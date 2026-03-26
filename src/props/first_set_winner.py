"""
First set winner model: Logistic regression predicting whether a player
wins the first set of a match.

Training target:
  - first_set_win = 1 if the player won the first set, 0 otherwise.
  - For match winner role: directly from parse_first_set_winner().
  - For match loser role: flipped (1 - parse_first_set_winner()).

Training features:
  - avg_ace_rate: service dominance proxy
  - opp_rtn_pct: opponent's return win percentage
  - surface_clay, surface_grass: one-hot encoded surface
  - level_G, level_M: one-hot encoded tournament level

Returns a 2-element PMF: [P(lose_first_set), P(win_first_set)].
"""

from __future__ import annotations

import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.props.score_parser import parse_first_set_winner
from src.props.base import save_prop_model


_FEATURE_COLS = [
    "avg_ace_rate",
    "opp_rtn_pct",
    "surface_clay",
    "surface_grass",
    "level_G",
    "level_M",
]


def _build_training_df(conn) -> pd.DataFrame:
    """
    Build training DataFrame by parsing match scores for first-set outcomes.

    Creates two rows per match (winner row + loser row), joining match_features
    for rolling rate features.

    Returns
    -------
    pd.DataFrame with columns: first_set_win, avg_ace_rate, opp_rtn_pct,
    surface_clay, surface_grass, level_G, level_M, match_date
    """
    query = """
        SELECT
            m.tourney_id,
            m.match_num,
            m.tour,
            m.score,
            m.tourney_date              AS match_date,
            mf_w.surface                AS surface,
            mf_w.tourney_level          AS tourney_level,
            -- Winner features
            mf_w.avg_ace_rate           AS w_avg_ace_rate,
            -- Loser features
            mf_l.avg_ace_rate           AS l_avg_ace_rate,
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
            match_date = row["match_date"]
            w_avg_ace_rate = row["w_avg_ace_rate"]
            l_avg_ace_rate = row["l_avg_ace_rate"]
            w_opp_rtn_pct = row["w_opp_rtn_pct"]
            l_opp_rtn_pct = row["l_opp_rtn_pct"]
        except (TypeError, IndexError):
            continue

        parsed = parse_first_set_winner(score_val)
        if parsed is None:
            continue

        # parsed=1 means match winner won first set; parsed=0 means match loser won it
        w_opp_rtn = w_opp_rtn_pct if w_opp_rtn_pct is not None else 0.35
        l_opp_rtn = l_opp_rtn_pct if l_opp_rtn_pct is not None else 0.35

        # Winner row: first_set_win = parsed (1 if winner won set 1, else 0)
        records.append({
            "first_set_win": parsed,
            "avg_ace_rate": w_avg_ace_rate or 0.0,
            "opp_rtn_pct": w_opp_rtn,
            "surface": surface,
            "tourney_level": tourney_level,
            "match_date": match_date,
        })
        # Loser row: first_set_win = 1 - parsed (flip perspective)
        records.append({
            "first_set_win": 1 - parsed,
            "avg_ace_rate": l_avg_ace_rate or 0.0,
            "opp_rtn_pct": l_opp_rtn,
            "surface": surface,
            "tourney_level": tourney_level,
            "match_date": match_date,
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
    Train the first_set_winner logistic regression model.

    Parameters
    ----------
    conn : sqlite3.Connection
    config : dict or None (unused, for registry compatibility)

    Returns
    -------
    dict with keys: model, family, alpha, aic
        alpha and aic are None (logistic regression, not a GLM count model).
    """
    df = _build_training_df(conn)
    if df.empty or len(df) < 10:
        raise ValueError("Insufficient training data for first_set_winner model (need at least 10 rows)")

    X = df[_FEATURE_COLS]
    y = df["first_set_win"]

    model = LogisticRegression(max_iter=500)
    model.fit(X, y)

    result = {
        "model": model,
        "family": "logistic",
        "alpha": None,
        "aic": None,
    }
    save_prop_model(result, "first_set_winner")
    return result


def predict(trained: dict, feature_row: dict) -> dict:
    """
    Predict first set winner probability for a single player-match.

    Parameters
    ----------
    trained : dict
        Return value of train() — contains "model", "family".
    feature_row : dict
        Keys: avg_ace_rate, opp_rtn_pct, surface, tourney_level.

    Returns
    -------
    dict with keys: pmf (list[float] of length 2), mu (float), model_version (str)
        pmf[0] = P(player loses first set)
        pmf[1] = P(player wins first set)
        mu = P(win first set)
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

    p_win = float(trained["model"].predict_proba(X)[0, 1])
    # 2-element PMF: [P(lose_first_set), P(win_first_set)]
    pmf = [1.0 - p_win, p_win]

    return {
        "pmf": pmf,
        "mu": p_win,
        "model_version": "logistic_v1",
    }
