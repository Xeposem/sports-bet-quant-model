"""XGBoost gradient boosting model with Optuna hyperparameter tuning.

Uses full match_features column set (XGB_FEATURES, 28 columns) per user decision.
Let XGBoost's tree splits discover which features matter -- no manual selection.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import numpy as np
import optuna
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from src.model.base import (
    XGB_FEATURES,
    augment_with_flipped,
    build_xgb_training_matrix,
    compute_time_weights,
    save_model,
    temporal_split,
)

logger = logging.getLogger(__name__)
optuna.logging.set_verbosity(optuna.logging.WARNING)


def _objective(trial, X_aug, y_aug, w_aug, n_splits=3):
    """Optuna objective: minimize Brier score via TimeSeriesSplit CV on augmented data."""
    params = {
        "n_estimators":     trial.suggest_int("n_estimators", 100, 500),
        "max_depth":        trial.suggest_int("max_depth", 3, 8),
        "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "subsample":        trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
    }
    clf = XGBClassifier(
        **params,
        eval_metric="logloss",
        random_state=42,
        verbosity=0,
    )
    tscv = TimeSeriesSplit(n_splits=n_splits)
    scores = []
    for train_idx, val_idx in tscv.split(X_aug):
        clf.fit(X_aug[train_idx], y_aug[train_idx],
                sample_weight=w_aug[train_idx])
        proba = clf.predict_proba(X_aug[val_idx])[:, 1]
        scores.append(brier_score_loss(y_aug[val_idx], proba))
    return float(np.mean(scores))


def train_fold(X_train, y_train, X_val, y_val, w_train, config=None):
    """Train XGBoost on pre-split data with Optuna + dual calibration.

    Accepts full XGB_FEATURES (28-column) arrays. Same signature pattern as
    logistic.train_and_calibrate for walk_forward.py compatibility.
    Returns (calibrated_model, metrics_dict).

    Parameters
    ----------
    X_train, y_train:
        Training features and labels (28 columns per XGB_FEATURES).
    X_val, y_val:
        Validation features and labels (used for calibration, not training).
    w_train:
        Time-decay sample weights for the training set.
    config:
        Optional dict. Supported keys:
            n_trials: int — number of Optuna trials (default 75).

    Returns
    -------
    (calibrated_model, metrics_dict)

    metrics_dict keys:
        calibration_method: 'sigmoid' or 'isotonic'
        val_brier_score: Brier score of the selected calibrator on validation set
        val_log_loss: log loss of the selected calibrator on validation set
        brier_sigmoid: Brier score of sigmoid calibrator
        brier_isotonic: Brier score of isotonic calibrator
        feature_importances: dict mapping XGB_FEATURES names to float importance values
        best_params: dict of Optuna-selected hyperparameters
    """
    if config is None:
        config = {}
    n_trials = config.get("n_trials", 75)

    # Augment training data with flipped rows so both classes are present
    X_aug, y_aug, w_aug = augment_with_flipped(
        X_train, y_train, w_train, XGB_FEATURES,
    )

    # Optuna hyperparameter search on augmented training split
    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    study.optimize(
        lambda trial: _objective(trial, X_aug, y_aug, w_aug),
        n_trials=n_trials,
        show_progress_bar=False,
    )
    best = study.best_params

    # Train final model with best params on full augmented training split
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", XGBClassifier(
            **best, eval_metric="logloss", random_state=42, verbosity=0
        )),
    ])
    pipeline.fit(X_aug, y_aug, clf__sample_weight=w_aug)

    # Extract feature importance before calibration wrapping
    xgb_step = pipeline.named_steps["clf"]
    # Use XGB_FEATURES names for feature importance labeling when dimensions match
    if X_train.shape[1] == len(XGB_FEATURES):
        feature_names = list(XGB_FEATURES)
    else:
        feature_names = [f"feature_{i}" for i in range(X_train.shape[1])]
    importances = dict(zip(feature_names, xgb_step.feature_importances_.tolist()))

    # Augment validation set for calibration fitting
    X_val_aug, y_val_aug, _ = augment_with_flipped(
        X_val, y_val, None, XGB_FEATURES,
    )

    # Dual calibration — sigmoid (Platt scaling) vs isotonic regression
    cal_sigmoid = CalibratedClassifierCV(FrozenEstimator(pipeline), method="sigmoid")
    cal_sigmoid.fit(X_val_aug, y_val_aug)
    proba_sig = cal_sigmoid.predict_proba(X_val)[:, 1]
    brier_sig = float(brier_score_loss(y_val, proba_sig))

    cal_isotonic = CalibratedClassifierCV(FrozenEstimator(pipeline), method="isotonic")
    cal_isotonic.fit(X_val_aug, y_val_aug)
    proba_iso = cal_isotonic.predict_proba(X_val)[:, 1]
    brier_iso = float(brier_score_loss(y_val, proba_iso))

    # Auto-select lower Brier score calibrator
    if brier_iso < brier_sig:
        best_model, best_method, best_brier = cal_isotonic, "isotonic", brier_iso
        best_proba = proba_iso
    else:
        best_model, best_method, best_brier = cal_sigmoid, "sigmoid", brier_sig
        best_proba = proba_sig

    best_logloss = float(log_loss(y_val, best_proba, labels=[0, 1]))

    metrics = {
        "calibration_method": best_method,
        "val_brier_score": best_brier,
        "val_log_loss": best_logloss,
        "brier_sigmoid": brier_sig,
        "brier_isotonic": brier_iso,
        "feature_importances": importances,
        "best_params": best,
    }
    return best_model, metrics


def train(conn, config=None):
    """Registry-compliant train: builds FULL feature matrix from DB, trains XGBoost.

    Uses build_xgb_training_matrix (28 columns) -- NOT build_training_matrix (12 columns).
    Per user decision: full match_features table, let XGBoost discover what matters.

    Parameters
    ----------
    conn:
        Open SQLite connection with match_features and matches tables populated.
    config:
        Optional config dict. Supported keys:
            n_trials: int — number of Optuna trials (default 75).

    Returns
    -------
    (calibrated_model, metrics_dict)
    """
    if config is None:
        config = {}
    X, y, match_dates = build_xgb_training_matrix(conn)
    weights = compute_time_weights(match_dates)
    split = temporal_split(X, y, weights, match_dates)
    return train_fold(
        split["X_train"], split["y_train"],
        split["X_val"], split["y_val"],
        split["w_train"], config,
    )


def predict(model, features):
    """Registry-compliant predict: returns dict with calibrated_prob.

    Parameters
    ----------
    model:
        Calibrated sklearn pipeline with predict_proba method.
    features:
        1-D or 2-D numpy array. If 1-D, reshaped to (1, n_features) internally.
        Should be a 28-dim XGB_FEATURES vector.

    Returns
    -------
    dict with key:
        calibrated_prob: float probability of winner outcome, in [0, 1]
    """
    if features.ndim == 1:
        features = features.reshape(1, -1)
    proba = model.predict_proba(features)
    prob = float(proba[0, 1])
    return {"calibrated_prob": prob}


def save_feature_importance(importances, fold_year, output_dir="models"):
    """Save feature importance dict as JSON file.

    Parameters
    ----------
    importances:
        Dict mapping feature names to float importance values.
    fold_year:
        Integer year label for the fold (used in filename).
    output_dir:
        Directory to write the JSON file. Created if it does not exist.

    Returns
    -------
    str: path to the written JSON file
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = os.path.join(output_dir, f"feature_importance_xgboost_v1_{fold_year}.json")
    with open(path, "w") as f:
        json.dump(importances, f, indent=2)
    return path
