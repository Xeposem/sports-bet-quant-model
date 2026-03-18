"""
Logistic regression model — registry-compliant interface plus backward-compatible
train_and_calibrate for walk_forward.py's per-fold use.

Registry interface:
  - train(conn, config=None) -> (model, metrics)
  - predict(model, features) -> dict with calibrated_prob

Backward-compatible:
  - train_and_calibrate(X_train, y_train, X_val, y_val, weights_train) -> (model, metrics)
    Used by walk_forward.py's run_fold which receives pre-split data.
"""

from __future__ import annotations

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.model.base import (
    LOGISTIC_FEATURES,
    build_training_matrix,
    compute_time_weights,
    temporal_split,
)


# ---------------------------------------------------------------------------
# Registry-compliant interface
# ---------------------------------------------------------------------------


def train(conn, config=None):
    """
    Train logistic regression with dual calibration.

    Registry-compliant signature: train(conn, config) -> (model, metrics).
    Internally calls build_training_matrix, compute_time_weights, temporal_split,
    then delegates to train_and_calibrate.

    Parameters
    ----------
    conn:
        Open SQLite connection with match_features and matches tables populated.
    config:
        Optional config dict — accepted for registry interface compatibility
        but not used for logistic regression.

    Returns
    -------
    (calibrated_model, metrics_dict)
    """
    X, y, match_dates = build_training_matrix(conn)
    weights = compute_time_weights(match_dates)
    split = temporal_split(X, y, weights, match_dates)
    model, metrics = train_and_calibrate(
        split["X_train"], split["y_train"],
        split["X_val"], split["y_val"],
        split["w_train"],
    )
    return model, metrics


def predict(model, features):
    """
    Predict using calibrated logistic model.

    Registry-compliant signature: predict(model, features) -> dict.

    Parameters
    ----------
    model:
        Calibrated sklearn pipeline with predict_proba method.
    features:
        1-D numpy array of shape (len(LOGISTIC_FEATURES),).

    Returns
    -------
    dict with key:
        calibrated_prob: float probability of winner outcome
    """
    proba = model.predict_proba(features.reshape(1, -1))
    prob = float(proba[0, 1])
    return {"calibrated_prob": prob}


# ---------------------------------------------------------------------------
# Backward-compatible standalone function (used by walk_forward.py)
# ---------------------------------------------------------------------------


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

    Used directly by walk_forward.py's run_fold (pre-split data) and internally
    by the registry train() wrapper.

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
