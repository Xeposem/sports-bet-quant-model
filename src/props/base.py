"""
Shared utilities for prop prediction models.

Key exports:
  - PROP_MODEL_DIR: directory for serialized prop models
  - compute_pmf: generate PMF array from Poisson or NegBin distribution
  - p_over: cumulative probability strictly above a threshold
  - save_prop_model / load_prop_model: joblib serialization
  - predict_and_store: batch predict and insert into prop_predictions table
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import List, Optional

import joblib
import numpy as np
import scipy.stats

PROP_MODEL_DIR = "models/props"


def compute_pmf(
    mu: float,
    family: str,
    alpha: float | None = None,
    max_k: int | None = None,
) -> list[float]:
    """
    Compute a probability mass function array for integer counts 0..max_k.

    Parameters
    ----------
    mu : float
        Mean of the distribution (expected value).
    family : str
        Distribution family. One of "poisson" or "negative_binomial".
    alpha : float or None
        Dispersion parameter for negative binomial. Required when family="negative_binomial".
        Ignored for Poisson.
    max_k : int or None
        Maximum count to include. Defaults to max(50, int(mu * 4)).

    Returns
    -------
    list of float
        PMF values for counts 0, 1, 2, ..., max_k. Sums to approximately 1.0.

    Examples
    --------
    >>> pmf = compute_pmf(6.0, "poisson")
    >>> abs(sum(pmf) - 1.0) < 0.001
    True
    """
    if max_k is None:
        max_k = max(50, int(mu * 6))

    k_values = np.arange(max_k + 1)

    if family == "poisson":
        pmf = scipy.stats.poisson.pmf(k_values, mu).tolist()
    elif family == "negative_binomial":
        if alpha is None or alpha <= 0:
            # Fallback to Poisson if alpha is invalid
            pmf = scipy.stats.poisson.pmf(k_values, mu).tolist()
        else:
            # Convert (mu, alpha) to scipy NegBin (n, p) params
            # statsmodels NegBin parameterization: Var = mu + alpha * mu^2
            # scipy parameterization: n=1/alpha, p=n/(n+mu)
            n = 1.0 / alpha
            p = n / (n + mu)
            pmf = scipy.stats.nbinom.pmf(k_values, n, p).tolist()
    else:
        raise ValueError(f"Unknown family: {family!r}. Expected 'poisson' or 'negative_binomial'.")

    return pmf


def p_over(pmf: list[float], threshold: float) -> float:
    """
    Compute cumulative probability strictly greater than threshold.

    Parameters
    ----------
    pmf : list of float
        PMF array where pmf[k] = P(X = k).
    threshold : float
        The line value. Returns P(X > threshold).

    Returns
    -------
    float
        Sum of pmf[k] for all k > threshold.

    Examples
    --------
    >>> p_over([0.1, 0.2, 0.3, 0.25, 0.15], 2.5)
    0.4
    >>> p_over([0.1, 0.2, 0.3, 0.25, 0.15], 2.0)
    0.4
    """
    k_min = int(threshold) + 1
    if k_min >= len(pmf):
        return 0.0
    return float(sum(pmf[k_min:]))


def save_prop_model(trained: dict, stat_type: str) -> str:
    """
    Serialize a trained prop model dict to disk.

    Parameters
    ----------
    trained : dict
        The trained model dictionary returned by a stat model's train() function.
    stat_type : str
        One of "aces", "double_faults", or "games_won".

    Returns
    -------
    str
        Path to the saved model file.
    """
    os.makedirs(PROP_MODEL_DIR, exist_ok=True)
    path = os.path.join(PROP_MODEL_DIR, f"{stat_type}_v1.joblib")
    joblib.dump(trained, path)
    return path


def load_prop_model(stat_type: str) -> dict:
    """
    Load a previously serialized prop model from disk.

    Parameters
    ----------
    stat_type : str
        One of "aces", "double_faults", or "games_won".

    Returns
    -------
    dict
        The trained model dictionary.

    Raises
    ------
    FileNotFoundError
        If no model has been saved for the given stat_type.
    """
    path = os.path.join(PROP_MODEL_DIR, f"{stat_type}_v1.joblib")
    return joblib.load(path)


def predict_and_store(
    conn,
    stat_types: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """
    Batch-predict props for all matches in a date range and insert into prop_predictions.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open database connection with prop_predictions table already created.
    stat_types : list of str or None
        Stat types to predict. Defaults to all keys in PROP_REGISTRY.
    date_from : str or None
        Start date (ISO "YYYY-MM-DD"). Defaults to 30 days before today.
    date_to : str or None
        End date (ISO "YYYY-MM-DD"). Defaults to today.

    Returns
    -------
    dict
        {"predicted": int, "stat_types": list of str}
    """
    # Import at function level to avoid circular import
    from src.props import PROP_REGISTRY

    from datetime import date, timedelta

    if stat_types is None:
        stat_types = list(PROP_REGISTRY.keys())
    if date_from is None:
        date_from = (date.today() - timedelta(days=30)).isoformat()
    if date_to is None:
        date_to = date.today().isoformat()

    total_predicted = 0

    for stat_type in stat_types:
        try:
            trained = load_prop_model(stat_type)
        except FileNotFoundError:
            # No model saved yet — skip gracefully
            continue

        # Query match data for the date range
        # match_stats has player_role ('winner'/'loser') not player_id
        # We join matches to get winner_id/loser_id and then denormalize
        query = """
            SELECT
                ms.tourney_id,
                ms.match_num,
                ms.tour,
                ms.player_role,
                m.tourney_date  AS match_date,
                t.surface,
                t.tourney_level,
                CASE ms.player_role WHEN 'winner' THEN m.winner_id ELSE m.loser_id END AS player_id,
                mf.avg_ace_rate,
                mf.avg_df_rate,
                -- Opponent return pct: other player's (first_won + second_won) / svpt
                ms_opp.first_won  + ms_opp.second_won  AS opp_rtn_won,
                ms_opp.svpt                             AS opp_svpt,
                -- Court speed index (D-04)
                COALESCE(csi.csi_value, 0.5)            AS court_speed_index,
                CASE WHEN csi.csi_value IS NULL THEN 1 ELSE 0 END AS has_no_csi,
                -- Pinnacle market probability (D-04)
                CASE ms.player_role
                    WHEN 'winner' THEN COALESCE(mf.pinnacle_prob_winner, 0.5)
                    ELSE COALESCE(mf.pinnacle_prob_loser, 0.5)
                END AS pinnacle_prob,
                COALESCE(mf.has_no_pinnacle, 1)         AS has_no_pinnacle,
                -- Opponent break point rate (D-07)
                CAST(COALESCE(ms_opp.bp_faced, 0) AS REAL)
                    / NULLIF(CAST(ms_opp.sv_gms AS REAL), 0) AS opp_bp_rate
            FROM match_stats ms
            JOIN matches m
              ON  ms.tourney_id = m.tourney_id
              AND ms.match_num  = m.match_num
              AND ms.tour       = m.tour
            JOIN tournaments t
              ON  t.tourney_id  = m.tourney_id
              AND t.tour        = m.tour
            JOIN match_features mf
              ON  mf.tourney_id   = ms.tourney_id
              AND mf.match_num    = ms.match_num
              AND mf.tour         = ms.tour
              AND mf.player_role  = ms.player_role
            LEFT JOIN match_stats ms_opp
              ON  ms_opp.tourney_id  = ms.tourney_id
              AND ms_opp.match_num   = ms.match_num
              AND ms_opp.tour        = ms.tour
              AND ms_opp.player_role != ms.player_role
            LEFT JOIN court_speed_index csi
              ON  csi.tourney_id = ms.tourney_id
              AND csi.tour       = ms.tour
            WHERE m.tourney_date BETWEEN ? AND ?
              AND m.match_type = 'completed'
        """
        rows = conn.execute(query, (date_from, date_to)).fetchall()

        for row in rows:
            player_id = row["player_id"]
            if player_id is None:
                continue

            # Build feature row for prediction
            opp_rtn_won = row["opp_rtn_won"]
            opp_svpt = row["opp_svpt"]
            if opp_rtn_won is not None and opp_svpt and opp_svpt > 0:
                opp_rtn_pct = float(opp_rtn_won) / float(opp_svpt)
            else:
                opp_rtn_pct = 0.35  # default

            feature_row = {
                "avg_ace_rate": row["avg_ace_rate"] or 0.0,
                "avg_df_rate": row["avg_df_rate"] or 0.0,
                "opp_rtn_pct": opp_rtn_pct,
                "surface": row["surface"] or "Hard",
                "tourney_level": row["tourney_level"] or "A",
                # New features (D-04)
                "court_speed_index": row["court_speed_index"] if row["court_speed_index"] is not None else 0.5,
                "has_no_csi": row["has_no_csi"] if row["has_no_csi"] is not None else 1,
                "pinnacle_prob": row["pinnacle_prob"] if row["pinnacle_prob"] is not None else 0.5,
                "has_no_pinnacle": row["has_no_pinnacle"] if row["has_no_pinnacle"] is not None else 1,
                "opp_bp_rate": row["opp_bp_rate"] if row["opp_bp_rate"] is not None else 0.15,
                # H2H defaults -- predict_and_store uses player avg as fallback
                "h2h_ace_rate": row["avg_ace_rate"] or 0.0,
                "h2h_games_rate": 0.0,
            }

            try:
                result = PROP_REGISTRY[stat_type]["predict"](trained, feature_row)
            except Exception:
                continue

            pmf = result["pmf"]
            mu = result["mu"]
            model_version = result.get("model_version", f"{stat_type}_v1")

            # Look up player_name
            player_row = conn.execute(
                "SELECT first_name, last_name FROM players WHERE player_id = ? LIMIT 1",
                (player_id,),
            ).fetchone()
            if player_row:
                player_name = f"{player_row['first_name'] or ''} {player_row['last_name'] or ''}".strip()
            else:
                player_name = str(player_id)

            conn.execute(
                """
                INSERT OR REPLACE INTO prop_predictions
                    (tour, player_id, player_name, stat_type, tourney_id, match_num,
                     match_date, mu, pmf_json, model_version, predicted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["tour"],
                    player_id,
                    player_name,
                    stat_type,
                    row["tourney_id"],
                    row["match_num"],
                    row["match_date"],
                    mu,
                    json.dumps(pmf),
                    model_version,
                    datetime.utcnow().isoformat(),
                ),
            )
            total_predicted += 1

        conn.commit()

    return {"predicted": total_predicted, "stat_types": stat_types}
