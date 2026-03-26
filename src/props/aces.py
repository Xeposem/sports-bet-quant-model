"""
Aces stat model: Poisson / NegBin GLM predicting ace count per player per match.

Training features:
  - avg_ace_rate: player's rolling average ace rate (aces/service points)
  - opp_rtn_pct: opponent's return win percentage ((first_won + second_won) / svpt)
  - surface_clay, surface_grass: one-hot encoded surface
  - level_G, level_M: one-hot encoded tournament level
  - court_speed_index: tournament court speed index (D-04)
  - has_no_csi: indicator when CSI is missing (D-04)
  - pinnacle_prob: devigged Pinnacle market probability (D-04)
  - has_no_pinnacle: indicator when Pinnacle odds are missing (D-04)
  - opp_bp_rate: opponent break point rate (D-07)
  - h2h_ace_rate: H2H head-to-head ace rate vs specific opponent (D-07)

Model selection: NegBin if nb_aic < poisson_aic - 2, else Poisson. (D-06)
Time-decay: exponential weighting with 365-day half-life. (D-08)
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
import statsmodels.api as sm

from src.props.base import compute_pmf, save_prop_model
from src.model.base import compute_time_weights


_FORMULA = (
    "ace_count ~ avg_ace_rate + opp_rtn_pct "
    "+ surface_clay + surface_grass + level_G + level_M "
    "+ court_speed_index + has_no_csi "
    "+ pinnacle_prob + has_no_pinnacle "
    "+ opp_bp_rate + h2h_ace_rate"
)


def _build_training_df(conn) -> pd.DataFrame:
    """
    Build training DataFrame from match_stats and match_features.

    Joins match_stats (ace counts per player_role) with match_features
    (rolling service rates) and match_stats for the opponent (return pct).
    Also joins court_speed_index and uses Pinnacle probs from match_features.
    Includes H2H ace rate subquery for opponent-specific adjustments.

    Returns
    -------
    pd.DataFrame with columns: ace_count, avg_ace_rate, opp_rtn_pct,
    surface_clay, surface_grass, level_G, level_M,
    court_speed_index, has_no_csi, pinnacle_prob, has_no_pinnacle,
    opp_bp_rate, h2h_ace_rate, match_date
    """
    query = """
        SELECT
            ms.ace                          AS ace_count,
            mf.avg_ace_rate                 AS avg_ace_rate,
            mf.surface                      AS surface,
            mf.tourney_level                AS tourney_level,
            -- Opponent return pct: (opp first_won + opp second_won) / opp svpt
            CAST(COALESCE(ms_opp.first_won, 0) + COALESCE(ms_opp.second_won, 0) AS REAL)
                / NULLIF(CAST(ms_opp.svpt AS REAL), 0) AS opp_rtn_pct,
            -- Match date for time-decay weights
            m.tourney_date                  AS match_date,
            -- Court speed index (D-04)
            COALESCE(csi.csi_value, 0.5)    AS court_speed_index,
            CASE WHEN csi.csi_value IS NULL THEN 1 ELSE 0 END AS has_no_csi,
            -- Pinnacle market probability (D-04)
            CASE ms.player_role
                WHEN 'winner' THEN COALESCE(mf.pinnacle_prob_winner, 0.5)
                ELSE COALESCE(mf.pinnacle_prob_loser, 0.5)
            END AS pinnacle_prob,
            COALESCE(mf.has_no_pinnacle, 1) AS has_no_pinnacle,
            -- Opponent break point rate (D-07)
            CAST(COALESCE(ms_opp.bp_faced, 0) AS REAL)
                / NULLIF(CAST(ms_opp.sv_gms AS REAL), 0) AS opp_bp_rate,
            -- H2H ace rate vs specific opponent (D-07, 3-match minimum)
            -- Returns NULL when fewer than 3 prior H2H matches exist
            (SELECT CASE WHEN COUNT(*) >= 3 THEN AVG(ms_h2h.ace * 1.0 / NULLIF(ms_h2h.svpt, 0)) ELSE NULL END
             FROM match_stats ms_h2h
             JOIN matches m_h2h
               ON ms_h2h.tourney_id = m_h2h.tourney_id
              AND ms_h2h.match_num  = m_h2h.match_num
              AND ms_h2h.tour       = m_h2h.tour
             WHERE m_h2h.tourney_date < m.tourney_date
               AND (
                 (ms_h2h.player_role = 'winner'
                  AND m_h2h.winner_id = CASE ms.player_role WHEN 'winner' THEN m.winner_id ELSE m.loser_id END
                  AND m_h2h.loser_id  = CASE ms.player_role WHEN 'winner' THEN m.loser_id ELSE m.winner_id END)
               OR
                 (ms_h2h.player_role = 'loser'
                  AND m_h2h.loser_id  = CASE ms.player_role WHEN 'winner' THEN m.winner_id ELSE m.loser_id END
                  AND m_h2h.winner_id = CASE ms.player_role WHEN 'winner' THEN m.loser_id ELSE m.winner_id END)
               )
            ) AS h2h_ace_rate
        FROM match_stats ms
        JOIN match_features mf
          ON  mf.tourney_id  = ms.tourney_id
          AND mf.match_num   = ms.match_num
          AND mf.tour        = ms.tour
          AND mf.player_role = ms.player_role
        JOIN matches m
          ON  m.tourney_id = ms.tourney_id
          AND m.match_num  = ms.match_num
          AND m.tour       = ms.tour
        LEFT JOIN match_stats ms_opp
          ON  ms_opp.tourney_id  = ms.tourney_id
          AND ms_opp.match_num   = ms.match_num
          AND ms_opp.tour        = ms.tour
          AND ms_opp.player_role != ms.player_role
        LEFT JOIN court_speed_index csi
          ON  csi.tourney_id = ms.tourney_id
          AND csi.tour       = ms.tour
        WHERE ms.ace IS NOT NULL
          AND mf.avg_ace_rate IS NOT NULL
    """
    rows = conn.execute(query).fetchall()
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        [dict(row) for row in rows],
        columns=[
            "ace_count", "avg_ace_rate", "surface", "tourney_level",
            "opp_rtn_pct", "match_date",
            "court_speed_index", "has_no_csi",
            "pinnacle_prob", "has_no_pinnacle",
            "opp_bp_rate", "h2h_ace_rate",
        ],
    )
    # Fill missing values
    df["opp_rtn_pct"] = df["opp_rtn_pct"].fillna(0.35)
    df["opp_bp_rate"] = df["opp_bp_rate"].fillna(0.15)
    df["court_speed_index"] = df["court_speed_index"].fillna(0.5)
    df["pinnacle_prob"] = df["pinnacle_prob"].fillna(0.5)
    df["has_no_csi"] = df["has_no_csi"].fillna(1)
    df["has_no_pinnacle"] = df["has_no_pinnacle"].fillna(1)
    # H2H fallback: use player's avg_ace_rate when <3 H2H matches
    df["h2h_ace_rate"] = df["h2h_ace_rate"].fillna(df["avg_ace_rate"])

    # One-hot encode surface and level
    df["surface_clay"] = (df["surface"] == "Clay").astype(int)
    df["surface_grass"] = (df["surface"] == "Grass").astype(int)
    df["level_G"] = (df["tourney_level"] == "G").astype(int)
    df["level_M"] = (df["tourney_level"] == "M").astype(int)

    return df


def train(conn, config=None) -> dict:
    """
    Train the aces GLM model on match_stats + match_features.

    Applies exponential time-decay weighting (D-08) and auto-selects
    between Poisson and NegBin via AIC comparison (D-06).

    Parameters
    ----------
    conn : sqlite3.Connection
    config : dict or None (unused, for registry compatibility)

    Returns
    -------
    dict with keys: model, family, alpha, aic
    """
    df = _build_training_df(conn)
    if df.empty or len(df) < 10:
        raise ValueError("Insufficient training data for aces model (need at least 10 rows)")

    # Exponential time-decay weighting (D-08): 365-day half-life
    weights = compute_time_weights(df["match_date"].tolist(), half_life_days=365)

    # Fit Poisson GLM with time-decay weights
    poisson_fit = smf.glm(
        formula=_FORMULA,
        data=df,
        family=sm.families.Poisson(),
    ).fit(var_weights=weights, disp=False)

    # Fit NegBin GLM with time-decay weights
    negbin_fit = smf.glm(
        formula=_FORMULA,
        data=df,
        family=sm.families.NegativeBinomial(),
    ).fit(var_weights=weights, disp=False)

    # Select family by AIC (prefer NegBin if meaningfully better) (D-06)
    if negbin_fit.aic < poisson_fit.aic - 2:
        chosen_fit = negbin_fit
        chosen_family = "negative_binomial"
        # statsmodels GLM NegBin: scale attribute holds the alpha dispersion parameter
        alpha = float(chosen_fit.scale)
    else:
        chosen_fit = poisson_fit
        chosen_family = "poisson"
        alpha = None

    result = {
        "model": chosen_fit,
        "family": chosen_family,
        "alpha": alpha,
        "aic": float(chosen_fit.aic),
    }
    save_prop_model(result, "aces")
    return result


def predict(trained: dict, feature_row: dict) -> dict:
    """
    Predict ace count PMF for a single player-match.

    Parameters
    ----------
    trained : dict
        Return value of train() — contains "model", "family", "alpha".
    feature_row : dict
        Keys: avg_ace_rate, opp_rtn_pct, surface, tourney_level,
        court_speed_index, has_no_csi, pinnacle_prob, has_no_pinnacle,
        opp_bp_rate, h2h_ace_rate.

    Returns
    -------
    dict with keys: pmf (list[float]), mu (float), model_version (str)
    """
    surface = feature_row.get("surface", "Hard")
    tourney_level = feature_row.get("tourney_level", "A")
    avg_ace_rate = feature_row.get("avg_ace_rate", 0.0)

    X = pd.DataFrame([{
        "avg_ace_rate": avg_ace_rate,
        "opp_rtn_pct": feature_row.get("opp_rtn_pct", 0.35),
        "surface_clay": 1 if surface == "Clay" else 0,
        "surface_grass": 1 if surface == "Grass" else 0,
        "level_G": 1 if tourney_level == "G" else 0,
        "level_M": 1 if tourney_level == "M" else 0,
        "court_speed_index": feature_row.get("court_speed_index", 0.5),
        "has_no_csi": feature_row.get("has_no_csi", 1),
        "pinnacle_prob": feature_row.get("pinnacle_prob", 0.5),
        "has_no_pinnacle": feature_row.get("has_no_pinnacle", 1),
        "opp_bp_rate": feature_row.get("opp_bp_rate", 0.15),
        # H2H fallback: use avg_ace_rate when no H2H data provided
        "h2h_ace_rate": feature_row.get("h2h_ace_rate") if feature_row.get("h2h_ace_rate") is not None else avg_ace_rate,
    }])

    mu = float(trained["model"].predict(X).iloc[0])
    pmf = compute_pmf(mu, trained["family"], trained.get("alpha"))

    return {
        "pmf": pmf,
        "mu": mu,
        "model_version": f"{trained['family']}_v1",
    }
