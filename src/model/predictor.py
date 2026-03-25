"""
Match prediction engine combining calibrated model probabilities with bookmaker odds
to compute expected value (EV) per match.

EV formula: EV = (calibrated_prob * decimal_odds) - 1
- Positive EV indicates a value bet (model sees more value than bookmaker)
- Negative EV indicates no edge

Key exports:
  - compute_ev: EV calculation for a single outcome
  - predict_match: Predictions for both players in one match
  - store_prediction: Idempotent INSERT OR REPLACE into predictions table
  - predict_all_matches: Batch prediction over all matches with features
"""

from __future__ import annotations

import logging
import math
import sqlite3
from datetime import datetime
from typing import Optional

import numpy as np

from src.model.base import LOGISTIC_FEATURES
from src.odds.devig import power_method_devig


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core EV formula
# ---------------------------------------------------------------------------


def compute_ev(calibrated_prob: float, decimal_odds: float) -> float:
    """
    Compute expected value for a single outcome.

    Formula: EV = (calibrated_prob * decimal_odds) - 1

    Args:
        calibrated_prob: Model probability (after calibration) for this outcome.
        decimal_odds: Decimal odds from bookmaker (e.g., 2.10).

    Returns:
        Float EV. Positive = value bet, negative = no edge.
    """
    return float(calibrated_prob * decimal_odds) - 1.0


# ---------------------------------------------------------------------------
# Match prediction
# ---------------------------------------------------------------------------

_FEATURE_QUERY = """
    SELECT
        w.tourney_id, w.match_num, w.tour,
        m.winner_id, m.loser_id,
        -- Winner feature vector (all LOGISTIC_FEATURES columns)
        COALESCE(w.elo_overall, 1500.0) - COALESCE(l.elo_overall, 1500.0)   AS elo_diff,
        COALESCE(w.elo_hard,    1500.0) - COALESCE(l.elo_hard,    1500.0)   AS elo_hard_diff,
        COALESCE(w.elo_clay,    1500.0) - COALESCE(l.elo_clay,    1500.0)   AS elo_clay_diff,
        COALESCE(w.elo_grass,   1500.0) - COALESCE(l.elo_grass,   1500.0)   AS elo_grass_diff,
        COALESCE(w.ranking, 0)       - COALESCE(l.ranking, 0)               AS ranking_diff,
        COALESCE(w.ranking_delta, 0) - COALESCE(l.ranking_delta, 0)         AS ranking_delta_diff,
        COALESCE(w.h2h_wins, 0)  - COALESCE(w.h2h_losses, 0)               AS h2h_balance,
        COALESCE(w.form_win_rate_10, 0.5) - COALESCE(l.form_win_rate_10, 0.5) AS form_diff_10,
        COALESCE(w.form_win_rate_20, 0.5) - COALESCE(l.form_win_rate_20, 0.5) AS form_diff_20,
        COALESCE(w.days_since_last, 0) - COALESCE(l.days_since_last, 0)     AS fatigue_diff,
        CASE WHEN COALESCE(w.elo_overall, 1500.0) = 1500.0 THEN 1 ELSE 0 END AS has_no_elo_w,
        CASE WHEN COALESCE(l.elo_overall, 1500.0) = 1500.0 THEN 1 ELSE 0 END AS has_no_elo_l,
        COALESCE(w.round_ordinal, 3) AS round_ordinal,
        COALESCE(w.best_of, 3) AS best_of,
        -- Pinnacle devigged probability differential (0 when no odds)
        COALESCE(w.pinnacle_prob_winner, 0.5) - COALESCE(l.pinnacle_prob_winner, 0.5) AS pinnacle_prob_diff,
        CASE WHEN w.pinnacle_prob_winner IS NULL THEN 1 ELSE 0 END AS has_no_pinnacle
    FROM match_features w
    JOIN match_features l
      ON  w.tourney_id = l.tourney_id
      AND w.match_num  = l.match_num
      AND w.tour       = l.tour
    JOIN matches m
      ON  w.tourney_id = m.tourney_id
      AND w.match_num  = m.match_num
      AND w.tour       = m.tour
    WHERE w.player_role = 'winner'
      AND l.player_role = 'loser'
      AND w.tourney_id  = ?
      AND w.match_num   = ?
      AND w.tour        = ?
"""

_ODDS_QUERY = """
    SELECT decimal_odds_a, decimal_odds_b
    FROM match_odds
    WHERE tourney_id = ?
      AND match_num  = ?
      AND tour       = ?
      AND bookmaker  = 'pinnacle'
    LIMIT 1
"""


def predict_match(
    model,
    conn: sqlite3.Connection,
    tourney_id: str,
    match_num: int,
    tour: str = "ATP",
    model_version: str = "logistic_v1",
) -> list:
    """
    Generate predictions for both players in a single match.

    Loads winner-loser feature differential from match_features, calls
    model.predict_proba to get P(winner wins). P(loser wins) = 1 - P(winner wins).
    If Pinnacle odds exist, computes devigged market probabilities and EV.
    If outcome is known (match already played), computes brier and log-loss contributions.

    Args:
        model: Calibrated sklearn pipeline with predict_proba method.
        conn: SQLite connection with schema applied.
        tourney_id: Tournament ID.
        match_num: Match number.
        tour: Tour identifier (default 'ATP').
        model_version: Model version string for the predictions PK.

    Returns:
        List of two dicts (one per player) with all predictions columns.
        Returns empty list if match_features are not found.
    """
    cursor = conn.execute(_FEATURE_QUERY, (tourney_id, match_num, tour))
    row = cursor.fetchone()
    if row is None:
        logger.warning(
            "No feature rows found for %s/%s/%s — skipping prediction",
            tourney_id, match_num, tour,
        )
        return []

    # Build feature vector from the differential columns
    # Columns start at index 5 (after tourney_id, match_num, tour, winner_id, loser_id)
    feature_vector = np.array(
        [row[i + 5] for i in range(len(LOGISTIC_FEATURES))],
        dtype=np.float64,
    ).reshape(1, -1)

    winner_id = row[3]
    loser_id = row[4]

    if winner_id is None or loser_id is None:
        logger.warning(
            "NULL player_id for %s/%s/%s — skipping prediction",
            tourney_id, match_num, tour,
        )
        return []

    # Get calibrated probability for winner (index 1 = P(class=1=winner))
    proba = model.predict_proba(feature_vector)
    prob_winner = float(proba[0, 1])
    prob_loser = 1.0 - prob_winner

    # For raw model probability, use the same value (calibrated pipeline)
    # The model IS the calibrated pipeline, so model_prob == calibrated_prob
    model_prob_winner = prob_winner
    model_prob_loser = prob_loser

    # Fetch Pinnacle odds
    odds_row = conn.execute(_ODDS_QUERY, (tourney_id, match_num, tour)).fetchone()

    pinnacle_prob_a: Optional[float] = None
    pinnacle_prob_b: Optional[float] = None
    decimal_odds_a: Optional[float] = None
    decimal_odds_b: Optional[float] = None
    ev_a: Optional[float] = None
    ev_b: Optional[float] = None
    edge_a: Optional[float] = None
    edge_b: Optional[float] = None

    if odds_row is not None:
        decimal_odds_a = float(odds_row[0])
        decimal_odds_b = float(odds_row[1])
        try:
            pinnacle_prob_a, pinnacle_prob_b = power_method_devig(decimal_odds_a, decimal_odds_b)
            ev_a = compute_ev(prob_winner, decimal_odds_a)
            ev_b = compute_ev(prob_loser, decimal_odds_b)
            edge_a = prob_winner - pinnacle_prob_a
            edge_b = prob_loser - pinnacle_prob_b
        except ValueError as exc:
            logger.warning("Devig failed for %s/%s: %s", tourney_id, match_num, exc)

    # Compute brier and log-loss contributions if outcome is known.
    # Outcome is always known for matches in the DB (winner_id is the winner).
    # winner has outcome=1, loser has outcome=0.
    brier_winner = (prob_winner - 1.0) ** 2
    brier_loser = (prob_loser - 0.0) ** 2

    # Per-sample log-loss: -[y*log(p) + (1-y)*log(1-p)]
    eps = 1e-15
    log_loss_winner = -math.log(max(prob_winner, eps))      # outcome=1
    log_loss_loser = -math.log(max(1.0 - prob_loser, eps))  # outcome=0 => log(1-p)

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    winner_pred = {
        "tourney_id": tourney_id,
        "match_num": match_num,
        "tour": tour,
        "player_id": winner_id,
        "model_version": model_version,
        "model_prob": model_prob_winner,
        "calibrated_prob": prob_winner,
        "brier_contribution": brier_winner,
        "log_loss_contribution": log_loss_winner,
        "pinnacle_prob": pinnacle_prob_a,
        "decimal_odds": decimal_odds_a,
        "ev_value": ev_a,
        "edge": edge_a,
        "predicted_at": now,
        "p5": None,
        "p50": None,
        "p95": None,
    }

    loser_pred = {
        "tourney_id": tourney_id,
        "match_num": match_num,
        "tour": tour,
        "player_id": loser_id,
        "model_version": model_version,
        "model_prob": model_prob_loser,
        "calibrated_prob": prob_loser,
        "brier_contribution": brier_loser,
        "log_loss_contribution": log_loss_loser,
        "pinnacle_prob": pinnacle_prob_b,
        "decimal_odds": decimal_odds_b,
        "ev_value": ev_b,
        "edge": edge_b,
        "predicted_at": now,
        "p5": None,
        "p50": None,
        "p95": None,
    }

    return [winner_pred, loser_pred]


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def store_prediction(conn: sqlite3.Connection, pred: dict) -> None:
    """
    INSERT OR REPLACE a prediction row into the predictions table.

    Idempotent — re-running prediction will update existing rows.
    CI columns (p5, p50, p95) default to None if not present in pred dict,
    so non-Bayesian callers with legacy dicts continue to work unchanged.

    Args:
        conn: SQLite connection.
        pred: Dict with predictions columns. p5/p50/p95 are optional (default None).
    """
    row = {
        "p5": None,
        "p50": None,
        "p95": None,
        **pred,
    }
    conn.execute(
        """
        INSERT OR REPLACE INTO predictions
            (tourney_id, match_num, tour, player_id, model_version,
             model_prob, calibrated_prob,
             brier_contribution, log_loss_contribution,
             pinnacle_prob, decimal_odds, ev_value, edge, predicted_at,
             p5, p50, p95)
        VALUES
            (:tourney_id, :match_num, :tour, :player_id, :model_version,
             :model_prob, :calibrated_prob,
             :brier_contribution, :log_loss_contribution,
             :pinnacle_prob, :decimal_odds, :ev_value, :edge, :predicted_at,
             :p5, :p50, :p95)
        """,
        row,
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Batch prediction
# ---------------------------------------------------------------------------

_ALL_MATCHES_QUERY = """
    SELECT DISTINCT w.tourney_id, w.match_num, w.tour
    FROM match_features w
    JOIN match_features l
      ON  w.tourney_id = l.tourney_id
      AND w.match_num  = l.match_num
      AND w.tour       = l.tour
    WHERE w.player_role = 'winner'
      AND l.player_role = 'loser'
    ORDER BY w.tourney_id, w.match_num
"""


def predict_all_matches(
    model,
    conn: sqlite3.Connection,
    model_version: str = "logistic_v1",
) -> dict:
    """
    Generate and store predictions for all matches that have feature rows.

    Calls predict_match for each match, then store_prediction for each
    resulting prediction dict.

    Args:
        model: Calibrated sklearn pipeline with predict_proba.
        conn: SQLite connection with match_features populated.
        model_version: Model version string for predictions PK.

    Returns:
        Dict with keys:
            matches_predicted: Number of matches processed.
            predictions_stored: Total prediction rows written (2 per match).
            with_ev: Number of matches where EV was computed (had Pinnacle odds).
    """
    cursor = conn.execute(_ALL_MATCHES_QUERY)
    matches = cursor.fetchall()

    # Build set of already-predicted matches so re-runs skip them
    already_done = set()
    for row in conn.execute(
        "SELECT tourney_id, match_num, tour FROM predictions WHERE model_version = ?",
        (model_version,),
    ).fetchall():
        already_done.add((row[0], row[1], row[2]))

    remaining = [m for m in matches if (m[0], m[1], m[2]) not in already_done]

    try:
        from tqdm import tqdm
        match_iter = tqdm(remaining, desc="Predicting", unit="match")
    except ImportError:
        match_iter = remaining

    matches_predicted = 0
    predictions_stored = 0
    with_ev = 0
    commit_interval = 1000

    for match_row in match_iter:
        tourney_id, match_num, tour = match_row[0], match_row[1], match_row[2]
        preds = predict_match(
            model, conn, tourney_id, match_num, tour=tour,
            model_version=model_version,
        )
        if not preds:
            continue

        matches_predicted += 1
        has_ev = False
        for pred in preds:
            store_prediction(conn, pred)
            predictions_stored += 1
            if pred["ev_value"] is not None:
                has_ev = True

        if has_ev:
            with_ev += 1

        if matches_predicted % commit_interval == 0:
            conn.commit()

    conn.commit()

    logger.info(
        "predict_all_matches: matches_predicted=%d, predictions_stored=%d, with_ev=%d (skipped %d already done)",
        matches_predicted, predictions_stored, with_ev, len(already_done),
    )
    return {
        "matches_predicted": matches_predicted,
        "predictions_stored": predictions_stored,
        "with_ev": with_ev,
    }
