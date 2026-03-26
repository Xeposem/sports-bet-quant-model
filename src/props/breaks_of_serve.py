"""
Breaks of serve stat model: Poisson / NegBin GLM predicting breaks of serve
(bp_faced - bp_saved) per player per match.

Training features:
  - avg_df_rate: player's rolling average double-fault rate (proxy for service pressure)
  - opp_rtn_pct: opponent's return win percentage
  - surface_clay, surface_grass: one-hot encoded surface
  - level_G, level_M: one-hot encoded tournament level

Model selection: NegBin if nb_aic < poisson_aic - 2, else Poisson.
"""

from __future__ import annotations

import pandas as pd
import statsmodels.formula.api as smf
import statsmodels.api as sm

from src.props.base import compute_pmf, save_prop_model


_FORMULA = (
    "breaks_suffered ~ avg_df_rate + opp_rtn_pct + surface_clay + surface_grass"
    " + level_G + level_M"
)


def _build_training_df(conn) -> pd.DataFrame:
    """
    Build training DataFrame from match_stats and match_features.

    Target variable: bp_faced - bp_saved (breaks of serve suffered).
    Joins match_stats with match_features for rolling rate features
    and opponent match_stats for return pct.

    Returns
    -------
    pd.DataFrame with columns: breaks_suffered, avg_df_rate, opp_rtn_pct,
    surface_clay, surface_grass, level_G, level_M
    """
    query = """
        SELECT
            (ms.bp_faced - COALESCE(ms.bp_saved, 0)) AS breaks_suffered,
            mf.avg_df_rate                            AS avg_df_rate,
            mf.surface                                AS surface,
            mf.tourney_level                          AS tourney_level,
            -- Opponent return pct: (opp first_won + opp second_won) / opp svpt
            CAST(COALESCE(ms_opp.first_won, 0) + COALESCE(ms_opp.second_won, 0) AS REAL)
                / NULLIF(CAST(ms_opp.svpt AS REAL), 0) AS opp_rtn_pct
        FROM match_stats ms
        JOIN match_features mf
          ON  mf.tourney_id  = ms.tourney_id
          AND mf.match_num   = ms.match_num
          AND mf.tour        = ms.tour
          AND mf.player_role = ms.player_role
        LEFT JOIN match_stats ms_opp
          ON  ms_opp.tourney_id  = ms.tourney_id
          AND ms_opp.match_num   = ms.match_num
          AND ms_opp.tour        = ms.tour
          AND ms_opp.player_role != ms.player_role
        WHERE ms.bp_faced IS NOT NULL
          AND mf.avg_df_rate IS NOT NULL
    """
    rows = conn.execute(query).fetchall()
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        [dict(row) for row in rows],
        columns=["breaks_suffered", "avg_df_rate", "surface", "tourney_level", "opp_rtn_pct"],
    )
    # Filter out negative values (shouldn't occur but guard against bad data)
    df = df[df["breaks_suffered"] >= 0].copy()

    # Fill missing opponent return pct with default
    df["opp_rtn_pct"] = df["opp_rtn_pct"].fillna(0.35)

    # One-hot encode surface and level
    df["surface_clay"] = (df["surface"] == "Clay").astype(int)
    df["surface_grass"] = (df["surface"] == "Grass").astype(int)
    df["level_G"] = (df["tourney_level"] == "G").astype(int)
    df["level_M"] = (df["tourney_level"] == "M").astype(int)

    return df


def train(conn, config=None) -> dict:
    """
    Train the breaks_of_serve GLM model on match_stats + match_features.

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
        raise ValueError("Insufficient training data for breaks_of_serve model (need at least 10 rows)")

    # Fit Poisson GLM
    poisson_fit = smf.glm(
        formula=_FORMULA,
        data=df,
        family=sm.families.Poisson(),
    ).fit(disp=False)

    # Fit NegBin GLM
    negbin_fit = smf.glm(
        formula=_FORMULA,
        data=df,
        family=sm.families.NegativeBinomial(),
    ).fit(disp=False)

    # Select family by AIC (prefer NegBin if meaningfully better)
    if negbin_fit.aic < poisson_fit.aic - 2:
        chosen_fit = negbin_fit
        chosen_family = "negative_binomial"
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
    save_prop_model(result, "breaks_of_serve")
    return result


def predict(trained: dict, feature_row: dict) -> dict:
    """
    Predict breaks of serve PMF for a single player-match.

    Parameters
    ----------
    trained : dict
        Return value of train() — contains "model", "family", "alpha".
    feature_row : dict
        Keys: avg_df_rate, opp_rtn_pct, surface, tourney_level.

    Returns
    -------
    dict with keys: pmf (list[float]), mu (float), model_version (str)
    """
    surface = feature_row.get("surface", "Hard")
    tourney_level = feature_row.get("tourney_level", "A")

    X = pd.DataFrame([{
        "avg_df_rate": feature_row.get("avg_df_rate", 0.0),
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
