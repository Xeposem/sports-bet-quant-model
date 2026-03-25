"""
Shared model utilities — feature constants, training matrix assembly,
time-decay weights, temporal split, model serialization.

Moved from trainer.py to provide a common foundation for all model types
in the registry-based architecture (logistic, xgboost, bayesian, ensemble).

Key exports:
  - LOGISTIC_FEATURES: curated feature list constant (16 entries)
  - build_training_matrix: assemble X, y, match_dates from match_features table
  - compute_time_weights: exponential time-decay sample weights
  - temporal_split: chronological 80/20 train/validation split
  - save_model / load_model: joblib serialization
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

import joblib
import numpy as np

# ---------------------------------------------------------------------------
# Feature list constant
# ---------------------------------------------------------------------------

#: Curated feature subset for the linear logistic regression model.
#: Ordered as they appear in the training matrix columns.
#: Differential features: winner_value - loser_value (or winner-perspective balance).
#: Indicator columns: boolean 0/1 flagging missing Elo (elo_overall == 1500.0 default).
LOGISTIC_FEATURES = [
    "elo_diff",           # overall Elo: winner - loser
    "elo_hard_diff",      # surface-specific Elo: Hard
    "elo_clay_diff",      # surface-specific Elo: Clay
    "elo_grass_diff",     # surface-specific Elo: Grass
    "ranking_diff",       # ATP ranking: winner.ranking - loser.ranking (lower = better)
    "ranking_delta_diff", # ranking change delta: winner.ranking_delta - loser.ranking_delta
    "h2h_balance",        # H2H balance from winner perspective: h2h_wins - h2h_losses
    "form_diff_10",       # rolling form (last 10): winner - loser
    "form_diff_20",       # rolling form (last 20): winner - loser
    "fatigue_diff",       # days since last match: winner.days_since_last - loser.days_since_last
    "has_no_elo_w",       # 1 if winner has default Elo (no real rating yet)
    "has_no_elo_l",       # 1 if loser has default Elo (no real rating yet)
    "round_ordinal",      # round stage (1=R128 .. 7=F), non-differential
    "best_of",            # best-of format (3 or 5), non-differential
    "pinnacle_prob_diff", # devigged Pinnacle prob: winner - loser (0 when no odds)
    "has_no_pinnacle",    # 1 if no Pinnacle odds available for this match
]

# ---------------------------------------------------------------------------
# SQL for assembling training matrix
# ---------------------------------------------------------------------------

_BUILD_MATRIX_SQL = """
    SELECT
        m.tourney_date,
        -- Elo differentials (COALESCE 1500 for NULL = default rating, so diff = 0)
        COALESCE(w.elo_overall, 1500.0) - COALESCE(l.elo_overall, 1500.0)   AS elo_diff,
        COALESCE(w.elo_hard,    1500.0) - COALESCE(l.elo_hard,    1500.0)   AS elo_hard_diff,
        COALESCE(w.elo_clay,    1500.0) - COALESCE(l.elo_clay,    1500.0)   AS elo_clay_diff,
        COALESCE(w.elo_grass,   1500.0) - COALESCE(l.elo_grass,   1500.0)   AS elo_grass_diff,
        -- Ranking differential (lower rank number = better, so sign convention kept raw)
        COALESCE(w.ranking, 0)       - COALESCE(l.ranking, 0)               AS ranking_diff,
        COALESCE(w.ranking_delta, 0) - COALESCE(l.ranking_delta, 0)         AS ranking_delta_diff,
        -- H2H balance: winner's net H2H record (wins minus losses)
        COALESCE(w.h2h_wins, 0)  - COALESCE(w.h2h_losses, 0)               AS h2h_balance,
        -- Form differentials (NULL -> 0.5 neutral win rate)
        COALESCE(w.form_win_rate_10, 0.5) - COALESCE(l.form_win_rate_10, 0.5) AS form_diff_10,
        COALESCE(w.form_win_rate_20, 0.5) - COALESCE(l.form_win_rate_20, 0.5) AS form_diff_20,
        -- Fatigue: days since last match differential
        COALESCE(w.days_since_last, 0) - COALESCE(l.days_since_last, 0)     AS fatigue_diff,
        -- Boolean indicators for missing Elo data (default Elo = 1500.0)
        CASE WHEN COALESCE(w.elo_overall, 1500.0) = 1500.0 THEN 1 ELSE 0 END AS has_no_elo_w,
        CASE WHEN COALESCE(l.elo_overall, 1500.0) = 1500.0 THEN 1 ELSE 0 END AS has_no_elo_l,
        -- Match context (non-differential, same for both players)
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
    ORDER BY m.tourney_date
"""


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def build_training_matrix(
    conn: sqlite3.Connection,
) -> tuple[np.ndarray, np.ndarray, list]:
    """
    Assemble the pairwise differential training matrix from match_features.

    Each row represents one match:
        X[i] = winner_features[i] - loser_features[i]   (for LOGISTIC_FEATURES subset)
        y[i] = 1.0  (always — winner-perspective differential)

    Parameters
    ----------
    conn:
        Open SQLite connection with match_features and matches tables populated.

    Returns
    -------
    X: ndarray of shape (n_matches, len(LOGISTIC_FEATURES))
    y: ndarray of shape (n_matches,) — all ones
    match_dates: list of ISO date strings, same order as rows (chronological)
    """
    cursor = conn.execute(_BUILD_MATRIX_SQL)
    rows = cursor.fetchall()
    if not rows:
        empty_X = np.empty((0, len(LOGISTIC_FEATURES)), dtype=np.float64)
        return empty_X, np.array([], dtype=np.float64), []

    match_dates: list[str] = [row[0] for row in rows]
    # Columns 1..len(LOGISTIC_FEATURES) are the feature values
    X = np.array([[row[i + 1] for i in range(len(LOGISTIC_FEATURES))] for row in rows],
                 dtype=np.float64)
    y = np.ones(len(rows), dtype=np.float64)
    return X, y, match_dates


def compute_time_weights(
    match_dates: list[str],
    half_life_days: int = 730,
    reference_date: Optional[str] = None,
) -> np.ndarray:
    """
    Compute exponential time-decay sample weights.

    Formula: weight = exp(-ln(2) * days_ago / half_life_days)

    Matches from exactly half_life_days ago receive weight ~0.5.
    Matches on the reference date receive weight 1.0.
    Weight is floored at 1e-6 (never exactly zero).

    Parameters
    ----------
    match_dates:
        List of ISO date strings (YYYY-MM-DD), one per training sample.
    half_life_days:
        Decay half-life. Default 730 (2 years).
    reference_date:
        Date used as "today" for computing days_ago. Defaults to the maximum
        date in match_dates (for reproducible training; tests may pass explicit date).

    Returns
    -------
    weights: ndarray of shape (len(match_dates),), values in (1e-6, 1.0]
    """
    if reference_date is not None:
        ref = date.fromisoformat(reference_date)
    else:
        # Default: reference = max date in list (reproducible for training)
        ref = max(date.fromisoformat(d) for d in match_dates)

    weights = []
    for d_str in match_dates:
        match_d = date.fromisoformat(d_str)
        days_ago = (ref - match_d).days
        # Clamp negative days_ago (future dates) to 0 so weight stays at 1.0
        days_ago = max(days_ago, 0)
        w = float(np.exp(-np.log(2) * days_ago / half_life_days))
        weights.append(max(w, 1e-6))
    return np.array(weights, dtype=np.float64)


def temporal_split(
    X: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    match_dates: list[str],
    train_ratio: float = 0.8,
) -> dict:
    """
    Chronological train/validation split (no shuffling).

    First train_ratio fraction of rows (by index) become training set.
    Remaining fraction become validation set.
    Assumes rows are already sorted chronologically (build_training_matrix guarantees this).

    Returns
    -------
    dict with keys: X_train, y_train, w_train, X_val, y_val, dates_train, dates_val
    """
    n = len(y)
    split_idx = int(np.floor(n * train_ratio))
    return {
        "X_train": X[:split_idx],
        "y_train": y[:split_idx],
        "w_train": weights[:split_idx],
        "X_val": X[split_idx:],
        "y_val": y[split_idx:],
        "dates_train": match_dates[:split_idx],
        "dates_val": match_dates[split_idx:],
    }


def augment_with_flipped(
    X: np.ndarray,
    y: np.ndarray,
    w: np.ndarray | None,
    feature_list: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Augment winner-perspective data with flipped (loser-perspective) rows.

    Differential features are negated; indicator columns (has_no_elo_w/l) are
    swapped; non-differential match-context columns are preserved unchanged.

    Returns (X_aug, y_aug, w_aug).
    """
    X_flip = -X.copy()

    # Swap has_no_elo_w <-> has_no_elo_l
    if "has_no_elo_w" in feature_list and "has_no_elo_l" in feature_list:
        idx_w = feature_list.index("has_no_elo_w")
        idx_l = feature_list.index("has_no_elo_l")
        X_flip[:, [idx_w, idx_l]] = X[:, [idx_l, idx_w]]

    # Restore non-differential (match-context) columns that should NOT be negated
    _NON_DIFF_COLS = [
        "surface_clay", "surface_grass", "surface_hard",
        "level_G", "level_M",
        "round_ordinal", "best_of",
        "has_no_pinnacle",
    ]
    for col in _NON_DIFF_COLS:
        if col in feature_list:
            idx = feature_list.index(col)
            X_flip[:, idx] = X[:, idx]

    # Interleave original and flipped rows so that sequential splits
    # (e.g. TimeSeriesSplit) always contain both classes.
    n = len(X)
    X_aug = np.empty((2 * n, X.shape[1]), dtype=X.dtype)
    X_aug[0::2] = X
    X_aug[1::2] = X_flip
    y_aug = np.empty(2 * n, dtype=y.dtype)
    y_aug[0::2] = y
    y_aug[1::2] = 1.0 - y
    if w is not None:
        w_aug = np.empty(2 * n, dtype=w.dtype)
        w_aug[0::2] = w
        w_aug[1::2] = w
    else:
        w_aug = None
    return X_aug, y_aug, w_aug


def save_model(calibrated_model, path: str) -> None:
    """Serialize calibrated model to a .joblib file."""
    joblib.dump(calibrated_model, path)


def load_model(path: str):
    """Load a previously serialized calibrated model from a .joblib file."""
    return joblib.load(path)


# ---------------------------------------------------------------------------
# XGBoost feature set — full match_features column set (27 pairwise features)
# ---------------------------------------------------------------------------

#: Full feature set for XGBoost gradient boosting model.
#: Uses ALL numeric match_features columns as pairwise winner-loser differentials,
#: plus one-hot encoded surface and tourney_level as match context.
#: Per user decision: "let XGBoost's tree splits discover which features matter".
XGB_FEATURES = [
    # --- Same 14 as LOGISTIC_FEATURES ---
    "elo_diff",           # elo_overall: winner - loser
    "elo_hard_diff",      # elo_hard: winner - loser
    "elo_clay_diff",      # elo_clay: winner - loser
    "elo_grass_diff",     # elo_grass: winner - loser
    "ranking_diff",       # ranking: winner - loser
    "ranking_delta_diff", # ranking_delta: winner - loser
    "h2h_balance",        # h2h_wins - h2h_losses (winner perspective)
    "form_diff_10",       # form_win_rate_10: winner - loser
    "form_diff_20",       # form_win_rate_20: winner - loser
    "fatigue_diff",       # days_since_last: winner - loser
    "has_no_elo_w",       # 1 if winner has default Elo
    "has_no_elo_l",       # 1 if loser has default Elo
    # --- Additional XGBoost features (from remaining match_features columns) ---
    "elo_overall_rd_diff",  # Glicko-2 rating deviation: winner - loser
    "elo_hard_rd_diff",     # Hard surface RD: winner - loser
    "elo_clay_rd_diff",     # Clay surface RD: winner - loser
    "elo_grass_rd_diff",    # Grass surface RD: winner - loser
    "h2h_surface_balance",  # h2h_surface_wins - h2h_surface_losses (winner perspective)
    "ace_rate_diff",        # avg_ace_rate: winner - loser
    "df_rate_diff",         # avg_df_rate: winner - loser
    "first_pct_diff",       # avg_first_pct: winner - loser
    "first_won_pct_diff",   # avg_first_won_pct: winner - loser
    "sets_7d_diff",         # sets_last_7_days: winner - loser
    "sentiment_diff",       # sentiment_score: winner - loser
    # --- Match context (non-differential, same for both players) ---
    "surface_clay",         # one-hot: 1 if surface=Clay
    "surface_grass",        # one-hot: 1 if surface=Grass
    "surface_hard",         # one-hot: 1 if surface=Hard
    "level_G",              # one-hot: 1 if tourney_level=G (Grand Slam)
    "level_M",              # one-hot: 1 if tourney_level=M (Masters)
    "round_ordinal",        # round stage (1=R128 .. 7=F)
    "best_of",              # best-of format (3 or 5)
    "pinnacle_prob_diff",   # devigged Pinnacle prob: winner - loser
    "has_no_pinnacle",      # 1 if no Pinnacle odds available
]

# ---------------------------------------------------------------------------
# SQL for assembling XGBoost training matrix (all match_features columns)
# ---------------------------------------------------------------------------

_BUILD_XGB_MATRIX_SQL = """
    SELECT
        m.tourney_date,
        -- Same 14 as logistic
        COALESCE(w.elo_overall, 1500.0) - COALESCE(l.elo_overall, 1500.0) AS elo_diff,
        COALESCE(w.elo_hard, 1500.0) - COALESCE(l.elo_hard, 1500.0) AS elo_hard_diff,
        COALESCE(w.elo_clay, 1500.0) - COALESCE(l.elo_clay, 1500.0) AS elo_clay_diff,
        COALESCE(w.elo_grass, 1500.0) - COALESCE(l.elo_grass, 1500.0) AS elo_grass_diff,
        COALESCE(w.ranking, 0) - COALESCE(l.ranking, 0) AS ranking_diff,
        COALESCE(w.ranking_delta, 0) - COALESCE(l.ranking_delta, 0) AS ranking_delta_diff,
        COALESCE(w.h2h_wins, 0) - COALESCE(w.h2h_losses, 0) AS h2h_balance,
        COALESCE(w.form_win_rate_10, 0.5) - COALESCE(l.form_win_rate_10, 0.5) AS form_diff_10,
        COALESCE(w.form_win_rate_20, 0.5) - COALESCE(l.form_win_rate_20, 0.5) AS form_diff_20,
        COALESCE(w.days_since_last, 0) - COALESCE(l.days_since_last, 0) AS fatigue_diff,
        CASE WHEN COALESCE(w.elo_overall, 1500.0) = 1500.0 THEN 1 ELSE 0 END AS has_no_elo_w,
        CASE WHEN COALESCE(l.elo_overall, 1500.0) = 1500.0 THEN 1 ELSE 0 END AS has_no_elo_l,
        -- Additional XGBoost features
        COALESCE(w.elo_overall_rd, 350.0) - COALESCE(l.elo_overall_rd, 350.0) AS elo_overall_rd_diff,
        COALESCE(w.elo_hard_rd, 350.0) - COALESCE(l.elo_hard_rd, 350.0) AS elo_hard_rd_diff,
        COALESCE(w.elo_clay_rd, 350.0) - COALESCE(l.elo_clay_rd, 350.0) AS elo_clay_rd_diff,
        COALESCE(w.elo_grass_rd, 350.0) - COALESCE(l.elo_grass_rd, 350.0) AS elo_grass_rd_diff,
        COALESCE(w.h2h_surface_wins, 0) - COALESCE(w.h2h_surface_losses, 0) AS h2h_surface_balance,
        COALESCE(w.avg_ace_rate, 0.0) - COALESCE(l.avg_ace_rate, 0.0) AS ace_rate_diff,
        COALESCE(w.avg_df_rate, 0.0) - COALESCE(l.avg_df_rate, 0.0) AS df_rate_diff,
        COALESCE(w.avg_first_pct, 0.0) - COALESCE(l.avg_first_pct, 0.0) AS first_pct_diff,
        COALESCE(w.avg_first_won_pct, 0.0) - COALESCE(l.avg_first_won_pct, 0.0) AS first_won_pct_diff,
        COALESCE(w.sets_last_7_days, 0) - COALESCE(l.sets_last_7_days, 0) AS sets_7d_diff,
        COALESCE(w.sentiment_score, 0.0) - COALESCE(l.sentiment_score, 0.0) AS sentiment_diff,
        -- One-hot surface (use winner's surface column, same for both)
        CASE WHEN w.surface = 'Clay' THEN 1 ELSE 0 END AS surface_clay,
        CASE WHEN w.surface = 'Grass' THEN 1 ELSE 0 END AS surface_grass,
        CASE WHEN w.surface = 'Hard' THEN 1 ELSE 0 END AS surface_hard,
        -- One-hot tourney_level
        CASE WHEN w.tourney_level = 'G' THEN 1 ELSE 0 END AS level_G,
        CASE WHEN w.tourney_level = 'M' THEN 1 ELSE 0 END AS level_M,
        -- Match context
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
    ORDER BY m.tourney_date
"""


def build_xgb_training_matrix(
    conn: sqlite3.Connection,
    train_end: Optional[str] = None,
) -> tuple[np.ndarray, np.ndarray, list]:
    """
    Assemble pairwise differential training matrix with ALL match_features columns.

    Like build_training_matrix but uses XGB_FEATURES (31 columns) instead of
    LOGISTIC_FEATURES (16). Includes RD diffs, serve stats, surface/level one-hots, pinnacle.

    Parameters
    ----------
    conn:
        Open SQLite connection with match_features and matches tables populated.
    train_end:
        Optional ISO date string. If provided, only rows with
        tourney_date < train_end are included (for walk-forward folds).
        If None, all rows are included (for full training).

    Returns
    -------
    X: ndarray of shape (n_matches, len(XGB_FEATURES))
    y: ndarray of shape (n_matches,) — all ones
    match_dates: list of ISO date strings
    """
    if train_end is not None:
        sql = _BUILD_XGB_MATRIX_SQL.replace(
            "ORDER BY m.tourney_date",
            "AND m.tourney_date < :train_end\n          ORDER BY m.tourney_date"
        )
        cursor = conn.execute(sql, {"train_end": train_end})
    else:
        cursor = conn.execute(_BUILD_XGB_MATRIX_SQL)
    rows = cursor.fetchall()
    if not rows:
        empty_X = np.empty((0, len(XGB_FEATURES)), dtype=np.float64)
        return empty_X, np.array([], dtype=np.float64), []
    match_dates = [row[0] for row in rows]
    X = np.array(
        [[row[i + 1] for i in range(len(XGB_FEATURES))] for row in rows],
        dtype=np.float64,
    )
    y = np.ones(len(rows), dtype=np.float64)
    return X, y, match_dates
