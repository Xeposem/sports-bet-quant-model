"""
Logistic regression training pipeline for tennis match outcome prediction.

Pairwise differential format: each training row = winner_features - loser_features.
Label is always 1 (winner-perspective). This avoids symmetry bias and double-counting.

Key exports:
  - LOGISTIC_FEATURES: curated feature list constant
  - build_training_matrix: assemble X, y, match_dates from match_features table
  - compute_time_weights: exponential time-decay sample weights
  - temporal_split: chronological 80/20 train/validation split
  - train_and_calibrate: StandardScaler + LogisticRegression + dual calibration
  - save_model / load_model: joblib serialization
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

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


def train_and_calibrate(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    weights_train: np.ndarray,
) -> tuple:
    """
    Train a StandardScaler + LogisticRegression pipeline, then calibrate using
    both Platt scaling (sigmoid) and isotonic regression on the validation set.
    Auto-selects whichever calibration method achieves the lower Brier score.

    Parameters
    ----------
    X_train, y_train:
        Training features and labels.
    X_val, y_val:
        Validation features and labels (used only for calibration, not training).
    weights_train:
        Time-decay sample weights for the training set.

    Returns
    -------
    (calibrated_model, metrics_dict)

    metrics_dict keys:
        calibration_method: 'sigmoid' or 'isotonic'
        val_brier_score: Brier score of the selected calibrator on validation set
        val_log_loss: log loss of the selected calibrator on validation set
        brier_sigmoid: Brier score of the sigmoid calibrator
        brier_isotonic: Brier score of the isotonic calibrator
    """
    # Step 1: Train base pipeline (scaler + logistic regression) on training set
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, C=1.0)),
    ])
    pipeline.fit(X_train, y_train, clf__sample_weight=weights_train)

    # Step 2: Freeze pipeline so calibrators train their own isotonic/sigmoid
    # mapping on the validation set without re-training the base model.
    # Use CalibratedClassifierCV(FrozenEstimator(pipeline)) — the preferred API
    # in sklearn >= 1.6 (cv='prefit' is deprecated as of 1.6, removed in 1.8).

    # Sigmoid (Platt scaling)
    cal_sigmoid = CalibratedClassifierCV(FrozenEstimator(pipeline), method="sigmoid")
    cal_sigmoid.fit(X_val, y_val)
    proba_sigmoid = cal_sigmoid.predict_proba(X_val)[:, 1]
    brier_sig = float(brier_score_loss(y_val, proba_sigmoid))

    # Isotonic regression
    cal_isotonic = CalibratedClassifierCV(FrozenEstimator(pipeline), method="isotonic")
    cal_isotonic.fit(X_val, y_val)
    proba_isotonic = cal_isotonic.predict_proba(X_val)[:, 1]
    brier_iso = float(brier_score_loss(y_val, proba_isotonic))

    # Step 3: Auto-select lower Brier score calibrator
    if brier_iso < brier_sig:
        best_model = cal_isotonic
        best_method = "isotonic"
        best_brier = brier_iso
        best_proba = proba_isotonic
    else:
        best_model = cal_sigmoid
        best_method = "sigmoid"
        best_brier = brier_sig
        best_proba = proba_sigmoid

    best_logloss = float(log_loss(y_val, best_proba))

    metrics = {
        "calibration_method": best_method,
        "val_brier_score": best_brier,
        "val_log_loss": best_logloss,
        "brier_sigmoid": brier_sig,
        "brier_isotonic": brier_iso,
    }
    return best_model, metrics


def save_model(calibrated_model, path: str) -> None:
    """Serialize calibrated model to a .joblib file."""
    joblib.dump(calibrated_model, path)


def load_model(path: str):
    """Load a previously serialized calibrated model from a .joblib file."""
    return joblib.load(path)
