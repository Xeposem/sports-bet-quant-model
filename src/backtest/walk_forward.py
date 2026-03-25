"""
Walk-forward backtesting engine with look-ahead bias prevention.

Implements chronological fold generation with expanding training windows,
per-fold model training, Kelly bet sizing, and bankroll tracking.

Key exports:
  - generate_folds: Chronological year-based fold generation
  - build_fold_training_matrix: Date-bounded training matrix
  - build_fold_test_matches: Test-window match/odds query
  - assert_no_look_ahead: Look-ahead contamination guard
  - run_fold: Single-fold train/predict/bet loop
  - run_walk_forward: Full walk-forward orchestration
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Optional

import numpy as np

from src.backtest.kelly import compute_kelly_bet, apply_bet_result
from src.model import MODEL_REGISTRY
from src.model.base import (
    build_xgb_training_matrix,
    XGB_FEATURES,
    compute_time_weights,
    temporal_split,
)
from src.model.predictor import compute_ev
from src.model.trainer import (
    LOGISTIC_FEATURES,
    compute_time_weights,
    temporal_split,
    train_and_calibrate,
)


logger = logging.getLogger(__name__)

# CLV sweep thresholds (D-07): candidate values to evaluate
SWEEP_THRESHOLDS = [0.01, 0.02, 0.03, 0.05, 0.07, 0.10]


# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

# Training matrix query: same pairwise differential as trainer._BUILD_MATRIX_SQL
# but adds AND m.tourney_date < :train_end to enforce the fold boundary.
_FOLD_MATRIX_SQL = """
    SELECT
        m.tourney_date,
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
        CASE WHEN COALESCE(l.elo_overall, 1500.0) = 1500.0 THEN 1 ELSE 0 END AS has_no_elo_l
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
      AND m.tourney_date < :train_end
    ORDER BY m.tourney_date
"""

_FOLD_TEST_MATCHES_SQL = """
    SELECT
        m.tourney_id, m.match_num, m.tour,
        m.winner_id, m.loser_id,
        m.tourney_date,
        w.surface, w.tourney_level,
        w.ranking  AS winner_rank,
        l.ranking  AS loser_rank,
        -- Feature vector columns (same differential as training)
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
        CASE WHEN w.pinnacle_prob_winner IS NULL THEN 1 ELSE 0 END AS has_no_pinnacle,
        w.pinnacle_prob_winner AS pinnacle_prob_market,
        o.decimal_odds_a, o.decimal_odds_b
    FROM match_features w
    JOIN match_features l
      ON  w.tourney_id = l.tourney_id
      AND w.match_num  = l.match_num
      AND w.tour       = l.tour
    JOIN matches m
      ON  w.tourney_id = m.tourney_id
      AND w.match_num  = m.match_num
      AND w.tour       = m.tour
    LEFT JOIN match_odds o
      ON  w.tourney_id = o.tourney_id
      AND w.match_num  = o.match_num
      AND w.tour       = o.tour
    WHERE w.player_role = 'winner'
      AND l.player_role = 'loser'
      AND m.tourney_date >= :test_start
      AND m.tourney_date <  :test_end
    ORDER BY m.tourney_date
"""

_FOLD_XGB_TEST_MATCHES_SQL = """
    SELECT
        m.tourney_id, m.match_num, m.tour,
        m.winner_id, m.loser_id,
        m.tourney_date,
        w.surface, w.tourney_level,
        w.ranking  AS winner_rank,
        l.ranking  AS loser_rank,
        -- Same 12 as logistic
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
        -- Additional XGBoost features
        COALESCE(w.elo_overall_rd, 350.0) - COALESCE(l.elo_overall_rd, 350.0) AS elo_overall_rd_diff,
        COALESCE(w.elo_hard_rd, 350.0) - COALESCE(l.elo_hard_rd, 350.0)       AS elo_hard_rd_diff,
        COALESCE(w.elo_clay_rd, 350.0) - COALESCE(l.elo_clay_rd, 350.0)       AS elo_clay_rd_diff,
        COALESCE(w.elo_grass_rd, 350.0) - COALESCE(l.elo_grass_rd, 350.0)     AS elo_grass_rd_diff,
        COALESCE(w.h2h_surface_wins, 0) - COALESCE(w.h2h_surface_losses, 0)   AS h2h_surface_balance,
        COALESCE(w.avg_ace_rate, 0.0)   - COALESCE(l.avg_ace_rate, 0.0)       AS ace_rate_diff,
        COALESCE(w.avg_df_rate, 0.0)    - COALESCE(l.avg_df_rate, 0.0)        AS df_rate_diff,
        COALESCE(w.avg_first_pct, 0.0)  - COALESCE(l.avg_first_pct, 0.0)      AS first_pct_diff,
        COALESCE(w.avg_first_won_pct, 0.0) - COALESCE(l.avg_first_won_pct, 0.0) AS first_won_pct_diff,
        COALESCE(w.sets_last_7_days, 0) - COALESCE(l.sets_last_7_days, 0)     AS sets_7d_diff,
        COALESCE(w.sentiment_score, 0.0) - COALESCE(l.sentiment_score, 0.0)   AS sentiment_diff,
        -- One-hot surface (match context, same for both players)
        CASE WHEN w.surface = 'Clay'  THEN 1 ELSE 0 END AS surface_clay,
        CASE WHEN w.surface = 'Grass' THEN 1 ELSE 0 END AS surface_grass,
        CASE WHEN w.surface = 'Hard'  THEN 1 ELSE 0 END AS surface_hard,
        -- One-hot tourney_level
        CASE WHEN w.tourney_level = 'G' THEN 1 ELSE 0 END AS level_G,
        CASE WHEN w.tourney_level = 'M' THEN 1 ELSE 0 END AS level_M,
        CASE WHEN w.pinnacle_prob_winner IS NULL THEN 1 ELSE 0 END AS has_no_pinnacle,
        w.pinnacle_prob_winner AS pinnacle_prob_market,
        o.decimal_odds_a, o.decimal_odds_b
    FROM match_features w
    JOIN match_features l
      ON  w.tourney_id = l.tourney_id
      AND w.match_num  = l.match_num
      AND w.tour       = l.tour
    JOIN matches m
      ON  w.tourney_id = m.tourney_id
      AND w.match_num  = m.match_num
      AND w.tour       = m.tour
    LEFT JOIN match_odds o
      ON  w.tourney_id = o.tourney_id
      AND w.match_num  = o.match_num
      AND w.tour       = o.tour
    WHERE w.player_role = 'winner'
      AND l.player_role = 'loser'
      AND m.tourney_date >= :test_start
      AND m.tourney_date <  :test_end
    ORDER BY m.tourney_date
"""

_COUNT_TRAINING_SQL = """
    SELECT COUNT(*)
    FROM match_features mf
    JOIN matches m USING (tourney_id, match_num, tour)
    WHERE m.tourney_date < :train_end
      AND mf.player_role = 'winner'
"""

_DISTINCT_TEST_YEARS_SQL = """
    SELECT DISTINCT CAST(substr(m.tourney_date, 1, 4) AS INTEGER) AS yr
    FROM match_features mf
    JOIN matches m USING (tourney_id, match_num, tour)
    WHERE mf.player_role = 'winner'
    ORDER BY yr
"""


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def generate_folds(
    conn: sqlite3.Connection,
    min_train_matches: int = 500,
) -> list[tuple[str, str, str]]:
    """
    Generate year-based walk-forward folds with expanding training windows.

    Each fold covers one calendar year as the test period.
    Training data = all matches before that year.

    Parameters
    ----------
    conn:
        Open SQLite connection with match_features and matches populated.
    min_train_matches:
        Minimum number of training rows required to include a fold.
        Folds with fewer training rows are skipped.

    Returns
    -------
    List of (train_end, test_start, test_end) tuples, chronologically ordered.
    train_end == test_start for each fold (no overlap, expanding window).
    """
    cursor = conn.execute(_DISTINCT_TEST_YEARS_SQL)
    years = [row[0] for row in cursor.fetchall()]

    folds = []
    for year in years:
        train_end = f"{year}-01-01"
        test_start = f"{year}-01-01"
        test_end = f"{year + 1}-01-01"

        # Count training rows available before this fold's start
        count_row = conn.execute(_COUNT_TRAINING_SQL, {"train_end": train_end}).fetchone()
        n_train = count_row[0] if count_row else 0

        if n_train < min_train_matches:
            logger.debug(
                "Skipping fold %d: only %d training rows (min=%d)",
                year, n_train, min_train_matches,
            )
            continue

        folds.append((train_end, test_start, test_end))

    return folds


def build_fold_training_matrix(
    conn: sqlite3.Connection,
    train_end: str,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """
    Assemble the pairwise differential training matrix for a fold.

    Identical to trainer.build_training_matrix but filtered to
    matches before train_end to prevent look-ahead bias.

    Parameters
    ----------
    conn:
        Open SQLite connection.
    train_end:
        ISO date string (YYYY-MM-DD). Only rows with tourney_date < train_end
        are included.

    Returns
    -------
    X: ndarray of shape (n_matches, len(LOGISTIC_FEATURES))
    y: ndarray of shape (n_matches,) — all ones (winner-perspective)
    match_dates: list of ISO date strings (chronological)
    """
    cursor = conn.execute(_FOLD_MATRIX_SQL, {"train_end": train_end})
    rows = cursor.fetchall()
    if not rows:
        empty_X = np.empty((0, len(LOGISTIC_FEATURES)), dtype=np.float64)
        return empty_X, np.array([], dtype=np.float64), []

    match_dates: list[str] = [row[0] for row in rows]
    X = np.array(
        [[row[i + 1] for i in range(len(LOGISTIC_FEATURES))] for row in rows],
        dtype=np.float64,
    )
    y = np.ones(len(rows), dtype=np.float64)
    return X, y, match_dates


def build_fold_test_matches(
    conn: sqlite3.Connection,
    test_start: str,
    test_end: str,
) -> list[dict]:
    """
    Query all matches in the test window.

    Returns a list of dicts containing match identifiers, context, feature vector,
    and odds (if available). Matches without odds have decimal_odds_a/b = None.

    Parameters
    ----------
    conn:
        Open SQLite connection.
    test_start:
        ISO date string (YYYY-MM-DD). Inclusive lower bound.
    test_end:
        ISO date string (YYYY-MM-DD). Exclusive upper bound.

    Returns
    -------
    List of match dicts with keys:
        tourney_id, match_num, tour, winner_id, loser_id, tourney_date,
        surface, tourney_level, winner_rank, loser_rank,
        features (np.ndarray), decimal_odds_a, decimal_odds_b, has_odds
    """
    cursor = conn.execute(
        _FOLD_TEST_MATCHES_SQL,
        {"test_start": test_start, "test_end": test_end},
    )
    rows = cursor.fetchall()

    matches = []
    for row in rows:
        # Columns: 0=tourney_id, 1=match_num, 2=tour, 3=winner_id, 4=loser_id,
        #          5=tourney_date, 6=surface, 7=tourney_level, 8=winner_rank,
        #          9=loser_rank, 10..21=feature columns (12 LOGISTIC_FEATURES),
        #          22=has_no_pinnacle, 23=pinnacle_prob_market,
        #          24=decimal_odds_a, 25=decimal_odds_b
        feature_start = 10
        feature_vec = np.array(
            [row[feature_start + i] for i in range(len(LOGISTIC_FEATURES))],
            dtype=np.float64,
        )
        odds_offset = feature_start + len(LOGISTIC_FEATURES)
        pinnacle_prob_market = row[odds_offset + 1]  # pinnacle_prob_market
        decimal_odds_a = row[odds_offset + 2]
        decimal_odds_b = row[odds_offset + 3]
        has_odds = (decimal_odds_a is not None and decimal_odds_b is not None)

        matches.append({
            "tourney_id": row[0],
            "match_num": row[1],
            "tour": row[2],
            "winner_id": row[3],
            "loser_id": row[4],
            "tourney_date": row[5],
            "surface": row[6],
            "tourney_level": row[7],
            "winner_rank": row[8],
            "loser_rank": row[9],
            "features": feature_vec,
            "pinnacle_prob_market": pinnacle_prob_market,
            "decimal_odds_a": decimal_odds_a,
            "decimal_odds_b": decimal_odds_b,
            "has_odds": has_odds,
        })
    return matches


def build_fold_xgb_test_matches(
    conn: sqlite3.Connection,
    test_start: str,
    test_end: str,
) -> list[dict]:
    """
    Query test matches with 27/28-column XGB_FEATURES vectors.

    Same structure as build_fold_test_matches but produces XGB_FEATURES-column
    feature vectors required by XGBoost, instead of 12-column LOGISTIC_FEATURES vectors.

    Parameters
    ----------
    conn:
        Open SQLite connection.
    test_start:
        ISO date string (YYYY-MM-DD). Inclusive lower bound.
    test_end:
        ISO date string (YYYY-MM-DD). Exclusive upper bound.

    Returns
    -------
    List of match dicts with keys:
        tourney_id, match_num, tour, winner_id, loser_id, tourney_date,
        surface, tourney_level, winner_rank, loser_rank,
        features (np.ndarray of len(XGB_FEATURES) columns),
        decimal_odds_a, decimal_odds_b, has_odds
    """
    cursor = conn.execute(
        _FOLD_XGB_TEST_MATCHES_SQL,
        {"test_start": test_start, "test_end": test_end},
    )
    rows = cursor.fetchall()

    matches = []
    for row in rows:
        # Columns: 0=tourney_id, 1=match_num, 2=tour, 3=winner_id, 4=loser_id,
        #          5=tourney_date, 6=surface, 7=tourney_level, 8=winner_rank,
        #          9=loser_rank, 10..10+len(XGB_FEATURES)-1=XGB feature columns,
        #          then has_no_pinnacle, pinnacle_prob_market, decimal_odds_a, decimal_odds_b
        feature_start = 10
        feature_vec = np.array(
            [row[feature_start + i] for i in range(len(XGB_FEATURES))],
            dtype=np.float64,
        )
        odds_offset = feature_start + len(XGB_FEATURES)
        pinnacle_prob_market = row[odds_offset + 1]  # pinnacle_prob_market
        decimal_odds_a = row[odds_offset + 2]
        decimal_odds_b = row[odds_offset + 3]
        has_odds = (decimal_odds_a is not None and decimal_odds_b is not None)

        matches.append({
            "tourney_id": row[0],
            "match_num": row[1],
            "tour": row[2],
            "winner_id": row[3],
            "loser_id": row[4],
            "tourney_date": row[5],
            "surface": row[6],
            "tourney_level": row[7],
            "winner_rank": row[8],
            "loser_rank": row[9],
            "features": feature_vec,
            "pinnacle_prob_market": pinnacle_prob_market,
            "decimal_odds_a": decimal_odds_a,
            "decimal_odds_b": decimal_odds_b,
            "has_odds": has_odds,
        })
    return matches


def assert_no_look_ahead(
    train_dates: list[str],
    test_dates: list[str],
) -> None:
    """
    Assert that no test period dates appear in the training set.

    Raises AssertionError if contamination is detected.

    Parameters
    ----------
    train_dates:
        List of ISO date strings from the training matrix.
    test_dates:
        List of ISO date strings from the test matches.
    """
    train_set = set(train_dates)
    overlap = [d for d in test_dates if d in train_set]
    if overlap:
        raise AssertionError(
            f"Look-ahead bias detected: {len(overlap)} test dates found in training data. "
            f"Overlapping dates (sample): {overlap[:5]}"
        )


def _train_model_for_fold(model_version, X_train, y_train, X_val, y_val,
                          w_train, config, conn=None, train_end=None):
    """Dispatch model training to the correct function based on model_version.

    For logistic_v1: uses pre-built 12-column X_train/X_val arrays
    For xgboost_v1: IGNORES pre-built arrays, calls build_xgb_training_matrix(conn, train_end)
                    to get XGB_FEATURES-column arrays, then temporal_split to get X_train/X_val
    For bayesian_v1: uses pre-built 12-column X_train/X_val arrays
    For ensemble_v1: trains each component with its correct feature dimensions

    Parameters
    ----------
    model_version: str model identifier
    X_train, y_train, X_val, y_val, w_train: pre-built 12-column logistic arrays
    config: dict with model-specific configuration
    conn: sqlite3.Connection (required for xgboost_v1 and ensemble_v1)
    train_end: str ISO date (required for xgboost_v1 and ensemble_v1)

    Returns (model_or_state, metrics_dict)
    """
    if model_version == "logistic_v1":
        return train_and_calibrate(X_train, y_train, X_val, y_val, w_train)

    elif model_version == "xgboost_v1":
        # XGBoost needs XGB_FEATURES-column arrays, NOT the 12-column logistic arrays.
        # Build fresh from DB using build_xgb_training_matrix.
        if conn is None or train_end is None:
            raise ValueError("xgboost_v1 requires conn and train_end for XGB feature matrix")
        from src.model.xgboost_model import train_fold as xgb_train_fold
        X_xgb, y_xgb, xgb_dates = build_xgb_training_matrix(conn, train_end)
        w_xgb = compute_time_weights(xgb_dates, reference_date=train_end)
        xgb_split = temporal_split(X_xgb, y_xgb, w_xgb, xgb_dates)
        return xgb_train_fold(
            xgb_split["X_train"], xgb_split["y_train"],
            xgb_split["X_val"], xgb_split["y_val"],
            xgb_split["w_train"], config,
        )

    elif model_version == "bayesian_v1":
        from src.model.bayesian import train_fold as bayes_train_fold
        result = bayes_train_fold(X_train, y_train, X_val, y_val, w_train, config=config)
        metrics = result.pop("metrics")
        return result, metrics

    elif model_version == "ensemble_v1":
        # Train each component model with its CORRECT feature dimensions.
        if conn is None or train_end is None:
            raise ValueError("ensemble_v1 requires conn and train_end")
        from src.model.xgboost_model import train_fold as xgb_train_fold
        from src.model.ensemble import compute_weights
        models = {}
        brier_scores = {}

        # --- Logistic: uses 12-column arrays (already provided) ---
        try:
            log_model, log_metrics = train_and_calibrate(
                X_train, y_train, X_val, y_val, w_train
            )
            models["logistic_v1"] = log_model
            brier_scores["logistic_v1"] = log_metrics["val_brier_score"]
        except Exception as exc:
            logger.warning("Ensemble fold: logistic failed: %s", exc)

        # --- XGBoost: needs XGB_FEATURES-column arrays from build_xgb_training_matrix ---
        try:
            X_xgb, y_xgb, xgb_dates = build_xgb_training_matrix(conn, train_end)
            w_xgb = compute_time_weights(xgb_dates, reference_date=train_end)
            xgb_split = temporal_split(X_xgb, y_xgb, w_xgb, xgb_dates)
            xgb_model, xgb_metrics = xgb_train_fold(
                xgb_split["X_train"], xgb_split["y_train"],
                xgb_split["X_val"], xgb_split["y_val"],
                xgb_split["w_train"], config,
            )
            models["xgboost_v1"] = xgb_model
            brier_scores["xgboost_v1"] = xgb_metrics["val_brier_score"]
        except Exception as exc:
            logger.warning("Ensemble fold: xgboost failed: %s", exc)

        # --- Bayesian: uses 12-column arrays (same as logistic) ---
        try:
            from src.model.bayesian import train_fold as bayes_train_fold
            bayes_result = bayes_train_fold(
                X_train, y_train, X_val, y_val, w_train, config=config
            )
            bayes_metrics = bayes_result.pop("metrics")
            if bayes_metrics.get("converged", False):
                models["bayesian_v1"] = bayes_result
                brier_scores["bayesian_v1"] = bayes_metrics["val_brier_score"]
            else:
                logger.warning(
                    "Ensemble fold: bayesian excluded (non-convergent, r_hat=%.3f)",
                    bayes_metrics.get("max_rhat", -1),
                )
        except Exception as exc:
            logger.warning("Ensemble fold: bayesian failed: %s", exc)

        weights = compute_weights(brier_scores)
        ensemble_state = {
            "models": models,
            "weights": weights,
            "brier_scores": brier_scores,
        }
        ensemble_metrics = {"val_brier_score": None, "component_weights": weights}
        return ensemble_state, ensemble_metrics

    else:
        raise ValueError(f"Unknown model_version: {model_version}")


def _predict_with_model(model_version, model_or_state, feature_vec,
                        xgb_feature_vec=None):
    """Predict using the trained model/state for a given model_version.

    Parameters
    ----------
    model_version: str model identifier
    model_or_state: trained model or ensemble state dict
    feature_vec: np.ndarray 12-column LOGISTIC_FEATURES vector (reshaped to 1xN)
    xgb_feature_vec: np.ndarray XGB_FEATURES-column vector (reshaped to 1xN).
                     Required when model_version is "xgboost_v1" or "ensemble_v1".

    Returns calibrated probability (float).
    """
    if model_version == "logistic_v1":
        proba = model_or_state.predict_proba(feature_vec)
        return float(proba[0, 1])

    elif model_version == "xgboost_v1":
        if xgb_feature_vec is None:
            raise ValueError("xgboost_v1 prediction requires xgb_feature_vec (XGB_FEATURES columns)")
        proba = model_or_state.predict_proba(xgb_feature_vec)
        return float(proba[0, 1])

    elif model_version == "bayesian_v1":
        from src.model.bayesian import predict as bayes_predict
        result = bayes_predict(model_or_state, feature_vec.flatten())
        return result["calibrated_prob"]

    elif model_version == "ensemble_v1":
        from src.model.ensemble import blend
        predictions = {}
        weights = model_or_state["weights"]
        for mk, m in model_or_state["models"].items():
            if mk not in weights:
                continue
            try:
                if mk == "logistic_v1":
                    proba = m.predict_proba(feature_vec)
                    predictions[mk] = float(proba[0, 1])
                elif mk == "xgboost_v1":
                    if xgb_feature_vec is None:
                        logger.warning("Ensemble predict: xgboost skipped, no xgb_feature_vec")
                        continue
                    proba = m.predict_proba(xgb_feature_vec)
                    predictions[mk] = float(proba[0, 1])
                elif mk == "bayesian_v1":
                    from src.model.bayesian import predict as bp
                    r = bp(m, feature_vec.flatten())
                    predictions[mk] = r["calibrated_prob"]
            except Exception as exc:
                logger.warning("Ensemble predict %s failed: %s", mk, exc)
        if not predictions:
            return 0.5
        avail_w = {k: weights[k] for k in predictions if k in weights}
        total = sum(avail_w.values())
        norm_w = ({k: v / total for k, v in avail_w.items()}
                  if total > 0 else {k: 1 / len(predictions) for k in predictions})
        return blend(predictions, norm_w)

    else:
        raise ValueError(f"Unknown model_version: {model_version}")


def run_fold(
    conn: sqlite3.Connection,
    train_end: str,
    test_start: str,
    test_end: str,
    bankroll: float,
    config: dict,
) -> tuple[list[dict], float]:
    """
    Execute a single walk-forward fold: train model, predict, size bets, update bankroll.

    Parameters
    ----------
    conn:
        Open SQLite connection.
    train_end:
        Training cutoff date (ISO YYYY-MM-DD). Exclusive upper bound for training data.
    test_start, test_end:
        Test window bounds.
    bankroll:
        Starting bankroll for this fold.
    config:
        Dict with keys: kelly_fraction, max_fraction, min_ev, model_version.

    Returns
    -------
    (results_rows, updated_bankroll)
        results_rows: list of dicts (one per bet decision per match side)
        updated_bankroll: bankroll after all bets in this fold
    """
    kelly_fraction = config.get("kelly_fraction", 0.25)
    max_fraction = config.get("max_fraction", 0.03)
    min_ev = config.get("min_ev", 0.0)
    clv_threshold = config.get("clv_threshold", 0.0)
    model_version = config.get("model_version", "logistic_v1")
    fold_year = int(test_start[:4])

    # Step 1: Build training matrix with date boundary
    X, y, train_dates = build_fold_training_matrix(conn, train_end)
    if len(y) == 0:
        logger.warning("Fold %s: empty training matrix, skipping", fold_year)
        return [], bankroll

    # Step 2: Compute time-decay weights with reference_date = train_end
    weights = compute_time_weights(train_dates, reference_date=train_end)

    # Step 3: Temporal split within training data
    split = temporal_split(X, y, weights, train_dates)

    # Need at least some validation data for calibration
    if len(split["y_val"]) < 2:
        logger.warning("Fold %s: insufficient validation data, skipping", fold_year)
        return [], bankroll

    # Step 4: Train model via dispatch (conn + train_end threaded for XGBoost/ensemble)
    try:
        model, _metrics = _train_model_for_fold(
            model_version, split["X_train"], split["y_train"],
            split["X_val"], split["y_val"], split["w_train"], config,
            conn=conn, train_end=train_end,
        )
    except Exception as exc:
        logger.error("Fold %s: training failed for %s: %s", fold_year, model_version, exc)
        return [], bankroll

    # Step 5: Get test matches
    test_matches = build_fold_test_matches(conn, test_start, test_end)

    # If model needs XGB_FEATURES-column features, fetch XGB test matches too
    xgb_test_matches = None
    xgb_features_by_match: dict = {}
    if model_version in ("xgboost_v1", "ensemble_v1"):
        xgb_test_matches = build_fold_xgb_test_matches(conn, test_start, test_end)
        # Build a lookup dict keyed by (tourney_id, match_num, tour) for fast pairing
        xgb_features_by_match = {
            (m["tourney_id"], m["match_num"], m["tour"]): m["features"]
            for m in xgb_test_matches
        }

    if not test_matches:
        logger.debug("Fold %s: no test matches found", fold_year)
        return [], bankroll

    # Look-ahead bias assertion (safety check)
    test_dates = [m["tourney_date"] for m in test_matches]
    assert_no_look_ahead(train_dates, test_dates)

    results_rows = []

    # Step 6: For each test match, predict and compute bets
    for match in test_matches:
        tourney_id = match["tourney_id"]
        match_num = match["match_num"]
        tour = match["tour"]
        winner_id = match["winner_id"]
        loser_id = match["loser_id"]
        feature_vec = match["features"].reshape(1, -1)

        # Get 27/28-column XGB feature vector if needed
        xgb_feature_vec = None
        if model_version in ("xgboost_v1", "ensemble_v1"):
            match_key = (tourney_id, match_num, tour)
            xgb_feat = xgb_features_by_match.get(match_key)
            if xgb_feat is not None:
                xgb_feature_vec = xgb_feat.reshape(1, -1)

        prob_winner = _predict_with_model(
            model_version, model, feature_vec,
            xgb_feature_vec=xgb_feature_vec,
        )
        prob_loser = 1.0 - prob_winner

        if not match["has_odds"]:
            # No odds: log as no-odds row for both perspectives, no bet
            for player_id, cal_prob in [(winner_id, prob_winner), (loser_id, prob_loser)]:
                results_rows.append({
                    "fold_year": fold_year,
                    "tourney_id": tourney_id,
                    "match_num": match_num,
                    "tour": tour,
                    "model_version": model_version,
                    "player_id": player_id,
                    "outcome": 1 if player_id == winner_id else 0,
                    "calibrated_prob": cal_prob,
                    "decimal_odds": 0.0,
                    "ev": 0.0,
                    "kelly_full": 0.0,
                    "kelly_bet": 0.0,
                    "flat_bet": 1.0,
                    "pnl_kelly": 0.0,
                    "pnl_flat": 0.0,
                    "bankroll_before": bankroll,
                    "bankroll_after": bankroll,
                    "surface": match["surface"],
                    "tourney_level": match["tourney_level"],
                    "winner_rank": match["winner_rank"],
                    "loser_rank": match["loser_rank"],
                    "tourney_date": match["tourney_date"],
                    "no_odds": True,
                })
            continue

        decimal_odds_a = float(match["decimal_odds_a"])  # odds for winner
        decimal_odds_b = float(match["decimal_odds_b"])  # odds for loser

        # Compute EV and Kelly bets for both sides
        ev_winner = compute_ev(prob_winner, decimal_odds_a)
        ev_loser = compute_ev(prob_loser, decimal_odds_b)

        # Extract CLV data from match dict (new columns added in Phase 13)
        pinnacle_prob_market = match.get("pinnacle_prob_market")
        has_no_pinnacle_flag = 1 if pinnacle_prob_market is None else 0
        pinnacle_prob_loser_side = (
            (1.0 - pinnacle_prob_market) if pinnacle_prob_market is not None else None
        )

        # Compute full Kelly (for logging) and fractional Kelly bet
        def _full_kelly(prob: float, decimal_odds: float) -> float:
            b = decimal_odds - 1.0
            return (b * prob - (1.0 - prob)) / b if b > 0 else 0.0

        kelly_full_winner = max(_full_kelly(prob_winner, decimal_odds_a), 0.0)
        kelly_full_loser = max(_full_kelly(prob_loser, decimal_odds_b), 0.0)

        kelly_bet_winner = compute_kelly_bet(
            prob_winner, decimal_odds_a, bankroll,
            kelly_fraction=kelly_fraction,
            max_fraction=max_fraction,
            min_ev=min_ev,
            clv_threshold=clv_threshold,
            pinnacle_prob=pinnacle_prob_market,
            has_no_pinnacle=has_no_pinnacle_flag,
        )
        kelly_bet_loser = compute_kelly_bet(
            prob_loser, decimal_odds_b, bankroll,
            kelly_fraction=kelly_fraction,
            max_fraction=max_fraction,
            min_ev=min_ev,
            clv_threshold=clv_threshold,
            pinnacle_prob=pinnacle_prob_loser_side,
            has_no_pinnacle=has_no_pinnacle_flag,
        )

        # Process winner-side bet
        bankroll_before_w = bankroll
        outcome_winner = 1  # winner_id is always the actual winner
        pnl_kelly_w = 0.0
        pnl_flat_w = 0.0

        if kelly_bet_winner > 0:
            pnl_kelly_w = kelly_bet_winner * (decimal_odds_a - 1.0)  # won
            pnl_flat_w = 1.0 * (decimal_odds_a - 1.0)  # flat bet won
            bankroll = apply_bet_result(bankroll, kelly_bet_winner, decimal_odds_a, won=True)

        results_rows.append({
            "fold_year": fold_year,
            "tourney_id": tourney_id,
            "match_num": match_num,
            "tour": tour,
            "model_version": model_version,
            "player_id": winner_id,
            "outcome": outcome_winner,
            "calibrated_prob": prob_winner,
            "decimal_odds": decimal_odds_a,
            "ev": ev_winner,
            "kelly_full": kelly_full_winner,
            "kelly_bet": kelly_bet_winner,
            "flat_bet": 1.0,
            "pnl_kelly": pnl_kelly_w,
            "pnl_flat": pnl_flat_w,
            "bankroll_before": bankroll_before_w,
            "bankroll_after": bankroll,
            "surface": match["surface"],
            "tourney_level": match["tourney_level"],
            "winner_rank": match["winner_rank"],
            "loser_rank": match["loser_rank"],
            "tourney_date": match["tourney_date"],
            "no_odds": False,
        })

        # Process loser-side bet
        bankroll_before_l = bankroll
        outcome_loser = 0  # loser_id never wins in historical data
        pnl_kelly_l = 0.0
        pnl_flat_l = 0.0

        if kelly_bet_loser > 0:
            pnl_kelly_l = -kelly_bet_loser  # lost (loser never wins)
            pnl_flat_l = -1.0  # flat bet lost
            bankroll = apply_bet_result(bankroll, kelly_bet_loser, decimal_odds_b, won=False)

        results_rows.append({
            "fold_year": fold_year,
            "tourney_id": tourney_id,
            "match_num": match_num,
            "tour": tour,
            "model_version": model_version,
            "player_id": loser_id,
            "outcome": outcome_loser,
            "calibrated_prob": prob_loser,
            "decimal_odds": decimal_odds_b,
            "ev": ev_loser,
            "kelly_full": kelly_full_loser,
            "kelly_bet": kelly_bet_loser,
            "flat_bet": 1.0,
            "pnl_kelly": pnl_kelly_l,
            "pnl_flat": pnl_flat_l,
            "bankroll_before": bankroll_before_l,
            "bankroll_after": bankroll,
            "surface": match["surface"],
            "tourney_level": match["tourney_level"],
            "winner_rank": match["winner_rank"],
            "loser_rank": match["loser_rank"],
            "tourney_date": match["tourney_date"],
            "no_odds": False,
        })

    return results_rows, bankroll


def run_walk_forward(
    conn: sqlite3.Connection,
    config: Optional[dict] = None,
) -> dict:
    """
    Execute the full walk-forward backtesting loop.

    Generates chronological year-based folds, runs each fold with an
    expanding training window, carries bankroll forward across folds,
    and stores all results in the backtest_results table.

    Parameters
    ----------
    conn:
        Open SQLite connection with match_features, matches, and match_odds populated.
    config:
        Optional configuration dict. Defaults:
            kelly_fraction=0.25, max_fraction=0.03, min_ev=0.0,
            initial_bankroll=1000.0, min_train_matches=500,
            model_version="logistic_v1".

    Returns
    -------
    Summary dict with keys:
        folds_run, total_bets, bets_placed, bets_skipped,
        total_pnl_kelly, total_pnl_flat, final_bankroll, start_bankroll.
    """
    if config is None:
        config = {}

    kelly_fraction = config.get("kelly_fraction", 0.25)
    max_fraction = config.get("max_fraction", 0.03)
    min_ev = config.get("min_ev", 0.0)
    clv_threshold = config.get("clv_threshold", 0.0)
    initial_bankroll = config.get("initial_bankroll", 1000.0)
    min_train_matches = config.get("min_train_matches", 500)
    model_version = config.get("model_version", "logistic_v1")

    fold_config = {
        "kelly_fraction": kelly_fraction,
        "max_fraction": max_fraction,
        "min_ev": min_ev,
        "clv_threshold": clv_threshold,
        "model_version": model_version,
    }

    folds = generate_folds(conn, min_train_matches=min_train_matches)
    logger.info("run_walk_forward: %d folds generated", len(folds))

    bankroll = initial_bankroll
    folds_run = 0
    total_bets = 0
    bets_placed = 0
    bets_skipped = 0
    total_pnl_kelly = 0.0
    total_pnl_flat = 0.0
    all_rows: list[dict] = []

    for train_end, test_start, test_end in folds:
        logger.info(
            "Running fold: train_end=%s, test=%s to %s, bankroll=%.2f",
            train_end, test_start, test_end, bankroll,
        )
        rows, bankroll = run_fold(
            conn, train_end, test_start, test_end, bankroll, fold_config
        )
        folds_run += 1

        for row in rows:
            if not row.get("no_odds"):
                total_bets += 1
                if row["kelly_bet"] > 0:
                    bets_placed += 1
                    total_pnl_kelly += row["pnl_kelly"]
                    total_pnl_flat += row["pnl_flat"]
                else:
                    bets_skipped += 1

        all_rows.extend(rows)

    # Store results in backtest_results table
    _store_backtest_results(conn, all_rows)

    summary = {
        "folds_run": folds_run,
        "total_bets": total_bets,
        "bets_placed": bets_placed,
        "bets_skipped": bets_skipped,
        "total_pnl_kelly": total_pnl_kelly,
        "total_pnl_flat": total_pnl_flat,
        "final_bankroll": bankroll,
        "start_bankroll": initial_bankroll,
    }

    logger.info(
        "run_walk_forward complete: folds=%d, bets_placed=%d, pnl_kelly=%.2f, "
        "final_bankroll=%.2f",
        folds_run, bets_placed, total_pnl_kelly, bankroll,
    )
    return summary


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _store_backtest_results(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """
    INSERT OR REPLACE all backtest result rows into backtest_results table.

    Parameters
    ----------
    conn:
        Open SQLite connection.
    rows:
        List of result dicts from run_fold. Rows with 'no_odds' are still stored.

    Returns
    -------
    int: Number of rows inserted.
    """
    if not rows:
        return 0

    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO backtest_results
                    (fold_year, tourney_id, match_num, tour, model_version,
                     player_id, outcome, calibrated_prob, decimal_odds, ev,
                     kelly_full, kelly_bet, flat_bet,
                     pnl_kelly, pnl_flat,
                     bankroll_before, bankroll_after,
                     surface, tourney_level, winner_rank, loser_rank, tourney_date)
                VALUES
                    (:fold_year, :tourney_id, :match_num, :tour, :model_version,
                     :player_id, :outcome, :calibrated_prob, :decimal_odds, :ev,
                     :kelly_full, :kelly_bet, :flat_bet,
                     :pnl_kelly, :pnl_flat,
                     :bankroll_before, :bankroll_after,
                     :surface, :tourney_level, :winner_rank, :loser_rank, :tourney_date)
                """,
                row,
            )
            inserted += 1
        except sqlite3.Error as exc:
            logger.warning("Failed to insert backtest row: %s — %s", row.get("tourney_id"), exc)

    conn.commit()
    return inserted


# ---------------------------------------------------------------------------
# CLV sweep functions (Phase 13, D-07, D-08)
# ---------------------------------------------------------------------------


def _compute_sweep_metrics(conn: sqlite3.Connection, model_version: str) -> tuple:
    """Compute Sharpe ratio and max drawdown from backtest_results for the given model.

    Parameters
    ----------
    conn:
        Open SQLite connection.
    model_version:
        Model version string to filter results.

    Returns
    -------
    Tuple of (sharpe: float, max_drawdown: float).
    """
    rows = conn.execute(
        "SELECT pnl_kelly, bankroll_after FROM backtest_results "
        "WHERE model_version = ? AND kelly_bet > 0 ORDER BY tourney_date, match_num",
        (model_version,),
    ).fetchall()
    if len(rows) < 2:
        return 0.0, 0.0

    pnls = [r[0] for r in rows]
    bankrolls = [r[1] for r in rows]

    # Sharpe = mean(pnl) / std(pnl): simple per-bet Sharpe ratio
    mean_pnl = sum(pnls) / len(pnls)
    std_pnl = (sum((p - mean_pnl) ** 2 for p in pnls) / len(pnls)) ** 0.5
    sharpe = mean_pnl / std_pnl if std_pnl > 0 else 0.0

    # Max drawdown from equity curve
    peak = bankrolls[0]
    max_dd = 0.0
    for b in bankrolls:
        if b > peak:
            peak = b
        dd = (peak - b) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    return sharpe, max_dd


def run_clv_sweep(
    conn: sqlite3.Connection,
    base_config: Optional[dict] = None,
    thresholds: Optional[list] = None,
) -> list:
    """
    Run walk-forward backtest at each CLV threshold value.

    Returns list of summary dicts, one per threshold.
    Each dict includes: clv_threshold, bets_placed, roi, sharpe, max_drawdown,
    total_pnl, final_bankroll.

    NOTE on DB side-effects: Each iteration calls run_walk_forward which
    writes to backtest_results. The last iteration's results remain in the
    DB. After sweep completes, the caller (CLI main() or API router) runs
    a final regular backtest at the user's configured clv_threshold, which
    overwrites backtest_results with the chosen threshold's data, leaving
    the DB in a consistent state.

    Parameters
    ----------
    conn:
        Open SQLite connection.
    base_config:
        Base configuration dict. Each sweep iteration adds/overrides clv_threshold.
    thresholds:
        List of CLV threshold values to sweep. Defaults to SWEEP_THRESHOLDS.

    Returns
    -------
    List of dicts, one per threshold, each with keys:
        clv_threshold, bets_placed, roi, sharpe, max_drawdown, total_pnl, final_bankroll.
    """
    if thresholds is None:
        thresholds = SWEEP_THRESHOLDS
    if base_config is None:
        base_config = {}

    results = []
    for thresh in thresholds:
        cfg = {**base_config, "clv_threshold": thresh}
        summary = run_walk_forward(conn, cfg)

        # Compute ROI: total_pnl / total_stake
        initial_bankroll = cfg.get("initial_bankroll", 1000.0)
        max_fraction = cfg.get("max_fraction", 0.03)
        bets_placed = summary.get("bets_placed", 0)
        total_stake = bets_placed * initial_bankroll * max_fraction if bets_placed > 0 else 1.0
        roi = summary.get("total_pnl_kelly", 0.0) / total_stake if total_stake > 0 else 0.0

        # Compute Sharpe and max_drawdown from backtest_results
        model_version = cfg.get("model_version", "logistic_v1")
        sharpe, max_dd = _compute_sweep_metrics(conn, model_version)

        results.append({
            "clv_threshold": thresh,
            "bets_placed": bets_placed,
            "roi": roi,
            "sharpe": sharpe,
            "max_drawdown": max_dd,
            "total_pnl": summary.get("total_pnl_kelly", 0.0),
            "final_bankroll": summary.get("final_bankroll", initial_bankroll),
        })

    return results
