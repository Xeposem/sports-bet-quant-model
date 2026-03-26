"""
Sets won stat model: Poisson / NegBin GLM predicting sets won per player per match.

Training data is assembled by parsing match scores via parse_sets() to extract
(winner_sets, loser_sets), then creating two rows per match (one per player).

Training features:
  - avg_ace_rate: proxy for service dominance
  - opp_rtn_pct: opponent's return win percentage
  - surface_clay, surface_grass: one-hot encoded surface
  - level_G, level_M: one-hot encoded tournament level
  - best_of: match format (3 or 5 sets) — critical covariate for set count

Model selection: NegBin if nb_aic < poisson_aic - 2, else Poisson.
predict() hard-caps PMF at max_k=6 (RESEARCH.md Pitfall 4).
"""

from __future__ import annotations

import pandas as pd
import statsmodels.formula.api as smf
import statsmodels.api as sm

from src.props.score_parser import parse_sets
from src.props.base import compute_pmf, save_prop_model


_FORMULA = (
    "sets_won ~ avg_ace_rate + opp_rtn_pct + surface_clay + surface_grass"
    " + level_G + level_M + best_of"
)


def _build_training_df(conn) -> pd.DataFrame:
    """
    Build training DataFrame by parsing match scores for set counts.

    Creates two rows per match (winner row + loser row), joining match_features
    for rolling rate features. Filters out retirements and incomplete matches.

    Returns
    -------
    pd.DataFrame with columns: sets_won, avg_ace_rate, opp_rtn_pct,
    surface_clay, surface_grass, level_G, level_M, best_of
    """
    query = """
        SELECT
            m.tourney_id,
            m.match_num,
            m.tour,
            m.score,
            COALESCE(mf_w.best_of, m.best_of, 3)   AS best_of,
            mf_w.surface                             AS surface,
            mf_w.tourney_level                       AS tourney_level,
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
        try:
            score_val = row["score"]
            surface = row["surface"]
            tourney_level = row["tourney_level"]
            best_of = row["best_of"] or 3
            w_avg_ace_rate = row["w_avg_ace_rate"]
            l_avg_ace_rate = row["l_avg_ace_rate"]
            w_opp_rtn_pct = row["w_opp_rtn_pct"]
            l_opp_rtn_pct = row["l_opp_rtn_pct"]
        except (TypeError, IndexError):
            continue

        parsed = parse_sets(score_val)
        if parsed is None:
            continue

        winner_sets, loser_sets = parsed

        w_opp_rtn = w_opp_rtn_pct if w_opp_rtn_pct is not None else 0.35
        l_opp_rtn = l_opp_rtn_pct if l_opp_rtn_pct is not None else 0.35

        # Winner row
        records.append({
            "sets_won": winner_sets,
            "avg_ace_rate": w_avg_ace_rate or 0.0,
            "opp_rtn_pct": w_opp_rtn,
            "surface": surface,
            "tourney_level": tourney_level,
            "best_of": int(best_of),
        })
        # Loser row
        records.append({
            "sets_won": loser_sets,
            "avg_ace_rate": l_avg_ace_rate or 0.0,
            "opp_rtn_pct": l_opp_rtn,
            "surface": surface,
            "tourney_level": tourney_level,
            "best_of": int(best_of),
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
    Train the sets_won GLM model on parsed match scores + match_features.

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
        raise ValueError("Insufficient training data for sets_won model (need at least 10 rows)")

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

    # Prefer NegBin if meaningfully better
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
    save_prop_model(result, "sets_won")
    return result


def predict(trained: dict, feature_row: dict) -> dict:
    """
    Predict sets won PMF for a single player-match.

    PMF is hard-capped at max_k=6 (per RESEARCH.md Pitfall 4 — sets bounded by best_of).

    Parameters
    ----------
    trained : dict
        Return value of train() — contains "model", "family", "alpha".
    feature_row : dict
        Keys: avg_ace_rate, opp_rtn_pct, surface, tourney_level, best_of.

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
        "best_of": feature_row.get("best_of", 3),
    }])

    mu = float(trained["model"].predict(X).iloc[0])
    # Hard-cap at max_k=6 — sets are bounded by best_of (max 5 sets in a match)
    pmf = compute_pmf(mu, trained["family"], trained.get("alpha"), max_k=6)

    return {
        "pmf": pmf,
        "mu": mu,
        "model_version": f"{trained['family']}_v1",
    }
