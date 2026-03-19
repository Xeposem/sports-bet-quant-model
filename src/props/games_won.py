"""
Games won stat model: NegBin GLM predicting total games won per player per match.

Training data is assembled by parsing match scores via parse_score() to extract
(winner_games, loser_games), then creating two rows per match (one per player).

Training features:
  - avg_ace_rate: proxy for service dominance (higher ace rate -> more games won)
  - opp_rtn_pct: opponent's return win percentage
  - surface_clay, surface_grass: one-hot encoded surface
  - level_G, level_M: one-hot encoded tournament level

Model preference: NegBin (higher variance due to match length variation).
Still compare AIC but prefer NegBin if comparable (nb_aic < poisson_aic + 2).
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import statsmodels.formula.api as smf
import statsmodels.api as sm

from src.props.score_parser import parse_score
from src.props.base import compute_pmf, save_prop_model


_FORMULA = "games_won ~ avg_ace_rate + opp_rtn_pct + surface_clay + surface_grass + level_G + level_M"


def _build_training_df(conn) -> pd.DataFrame:
    """
    Build training DataFrame by parsing match scores for game counts.

    Creates two rows per match (winner row + loser row), joining match_features
    for rolling rate features.

    Returns
    -------
    pd.DataFrame with columns: games_won, avg_ace_rate, opp_rtn_pct,
    surface_clay, surface_grass, level_G, level_M
    """
    # Query matches with scores and join match_features for both roles
    query = """
        SELECT
            m.tourney_id,
            m.match_num,
            m.tour,
            m.score,
            m.surface,
            m.tourney_level,
            -- Winner features
            mf_w.avg_ace_rate   AS w_avg_ace_rate,
            -- Loser features
            mf_l.avg_ace_rate   AS l_avg_ace_rate,
            -- Opponent return pct for winner (= loser's return pct)
            CAST(COALESCE(ms_l.first_won, 0) + COALESCE(ms_l.second_won, 0) AS REAL)
                / NULLIF(CAST(ms_l.svpt AS REAL), 0) AS w_opp_rtn_pct,
            -- Opponent return pct for loser (= winner's return pct)
            CAST(COALESCE(ms_w.first_won, 0) + COALESCE(ms_w.second_won, 0) AS REAL)
                / NULLIF(CAST(ms_w.svpt AS REAL), 0) AS l_opp_rtn_pct
        FROM matches m
        JOIN match_features mf_w
          ON  mf_w.tourney_id  = m.tourney_id
          AND mf_w.match_num   = m.match_num
          AND mf_w.tour        = m.tour
          AND mf_w.player_role = 'winner'
        JOIN match_features mf_l
          ON  mf_l.tourney_id  = m.tourney_id
          AND mf_l.match_num   = m.match_num
          AND mf_l.tour        = m.tour
          AND mf_l.player_role = 'loser'
        LEFT JOIN match_stats ms_w
          ON  ms_w.tourney_id  = m.tourney_id
          AND ms_w.match_num   = m.match_num
          AND ms_w.tour        = m.tour
          AND ms_w.player_role = 'winner'
        LEFT JOIN match_stats ms_l
          ON  ms_l.tourney_id  = m.tourney_id
          AND ms_l.match_num   = m.match_num
          AND ms_l.tour        = m.tour
          AND ms_l.player_role = 'loser'
        WHERE m.score IS NOT NULL
          AND m.match_type = 'completed'
          AND mf_w.avg_ace_rate IS NOT NULL
          AND mf_l.avg_ace_rate IS NOT NULL
    """
    rows = conn.execute(query).fetchall()
    if not rows:
        return pd.DataFrame()

    records = []
    for row in rows:
        score = row["score"] if hasattr(row, "__getitem__") else row[3]
        # Support both sqlite3.Row and dict-like access
        try:
            score_val = row["score"]
            surface = row["surface"]
            tourney_level = row["tourney_level"]
            w_avg_ace_rate = row["w_avg_ace_rate"]
            l_avg_ace_rate = row["l_avg_ace_rate"]
            w_opp_rtn_pct = row["w_opp_rtn_pct"]
            l_opp_rtn_pct = row["l_opp_rtn_pct"]
        except (TypeError, IndexError):
            continue

        parsed = parse_score(score_val)
        if parsed is None:
            continue

        winner_games, loser_games = parsed

        w_opp_rtn = w_opp_rtn_pct if w_opp_rtn_pct is not None else 0.35
        l_opp_rtn = l_opp_rtn_pct if l_opp_rtn_pct is not None else 0.35

        # Winner row
        records.append({
            "games_won": winner_games,
            "avg_ace_rate": w_avg_ace_rate or 0.0,
            "opp_rtn_pct": w_opp_rtn,
            "surface": surface,
            "tourney_level": tourney_level,
        })
        # Loser row
        records.append({
            "games_won": loser_games,
            "avg_ace_rate": l_avg_ace_rate or 0.0,
            "opp_rtn_pct": l_opp_rtn,
            "surface": surface,
            "tourney_level": tourney_level,
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["surface_clay"] = (df["surface"] == "Clay").astype(int)
    df["surface_grass"] = (df["surface"] == "Grass").astype(int)
    df["level_G"] = (df["tourney_level"] == "G").astype(int)
    df["level_M"] = (df["tourney_level"] == "M").astype(int)

    return df


def train(conn, config=None) -> dict:
    """
    Train the games_won GLM model on parsed match scores + match_features.

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
        raise ValueError("Insufficient training data for games_won model (need at least 10 rows)")

    poisson_fit = smf.glm(
        formula=_FORMULA,
        data=df,
        family=sm.families.Poisson(),
    ).fit(disp=False)

    negbin_fit = smf.glm(
        formula=_FORMULA,
        data=df,
        family=sm.families.NegativeBinomial(),
    ).fit(disp=False)

    # Prefer NegBin for games_won (higher variance due to match length)
    # Use NegBin unless Poisson is meaningfully better (poisson_aic < negbin_aic - 2)
    if poisson_fit.aic < negbin_fit.aic - 2:
        chosen_fit = poisson_fit
        chosen_family = "poisson"
        alpha = None
    else:
        chosen_fit = negbin_fit
        chosen_family = "negative_binomial"
        alpha = float(chosen_fit.scale)

    result = {
        "model": chosen_fit,
        "family": chosen_family,
        "alpha": alpha,
        "aic": float(chosen_fit.aic),
    }
    save_prop_model(result, "games_won")
    return result


def predict(trained: dict, feature_row: dict) -> dict:
    """
    Predict games won PMF for a single player-match.

    Parameters
    ----------
    trained : dict
        Return value of train() — contains "model", "family", "alpha".
    feature_row : dict
        Keys: avg_ace_rate, opp_rtn_pct, surface, tourney_level.

    Returns
    -------
    dict with keys: pmf (list[float]), mu (float), model_version (str)
    """
    surface = feature_row.get("surface", "Hard")
    tourney_level = feature_row.get("tourney_level", "A")

    X = pd.DataFrame([{
        "avg_ace_rate": feature_row.get("avg_ace_rate", 0.0),
        "opp_rtn_pct": feature_row.get("opp_rtn_pct", 0.35),
        "surface_clay": 1 if surface == "Clay" else 0,
        "surface_grass": 1 if surface == "Grass" else 0,
        "level_G": 1 if tourney_level == "G" else 0,
        "level_M": 1 if tourney_level == "M" else 0,
    }])

    mu = float(trained["model"].predict(X).iloc[0])
    pmf = compute_pmf(mu, trained["family"], trained.get("alpha"))

    return {
        "pmf": pmf,
        "mu": mu,
        "model_version": f"{trained['family']}_v1",
    }
