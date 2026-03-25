"""Ensemble model — inverse Brier score weighted blending of component models."""
from __future__ import annotations

import logging
import numpy as np

logger = logging.getLogger(__name__)

# Component model versions included in the ensemble
COMPONENT_MODELS = ["logistic_v1", "xgboost_v1", "bayesian_v1"]

# Pinnacle-augmented ensemble components (Phase 12)
PINNACLE_COMPONENT_MODELS = ["logistic_v3_pinnacle", "xgboost_v2_pinnacle"]


def compute_weights(brier_scores: dict) -> dict:
    """Compute inverse Brier score weights, normalized to sum=1.

    Parameters
    ----------
    brier_scores: dict mapping model_version -> float Brier score (or None if failed)

    Returns
    -------
    dict mapping model_version -> float weight. Models with None or 0 Brier are excluded.

    Raises
    ------
    ValueError if no valid Brier scores remain after filtering.
    """
    available = {k: v for k, v in brier_scores.items()
                 if v is not None and v > 0}
    if not available:
        raise ValueError("No valid Brier scores for ensemble weighting")
    raw = {k: 1.0 / v for k, v in available.items()}
    total = sum(raw.values())
    return {k: w / total for k, w in raw.items()}


def blend(predictions: dict, weights: dict) -> float:
    """Compute weighted average of model predictions.

    Parameters
    ----------
    predictions: dict mapping model_version -> float probability
    weights: dict mapping model_version -> float weight (sum to 1)

    Returns
    -------
    float: blended probability
    """
    return sum(predictions[k] * weights[k] for k in weights)


def train(conn, config=None):
    """Registry-compliant train: trains all component models, computes weights.

    Returns (ensemble_state, metrics) where ensemble_state contains
    trained component models and their weights.
    """
    from src.model import MODEL_REGISTRY
    from src.model.base import build_training_matrix, compute_time_weights, temporal_split

    if config is None:
        config = {}

    X, y, match_dates = build_training_matrix(conn)
    weights = compute_time_weights(match_dates)
    split = temporal_split(X, y, weights, match_dates)

    trained_models = {}
    brier_scores = {}

    for model_key in COMPONENT_MODELS:
        if model_key not in MODEL_REGISTRY:
            logger.warning("Component model %s not in registry, skipping", model_key)
            continue
        try:
            entry = MODEL_REGISTRY[model_key]
            model, metrics = entry["train"](conn, config.get(model_key, {}))
            trained_models[model_key] = {"model": model, "predict": entry["predict"]}
            brier_scores[model_key] = metrics.get("val_brier_score")
            logger.info("Ensemble component %s: brier=%.4f",
                       model_key, brier_scores[model_key] or -1)
        except Exception as exc:
            logger.warning("Ensemble component %s failed: %s", model_key, exc)
            brier_scores[model_key] = None

    ensemble_weights = compute_weights(brier_scores)

    ensemble_state = {
        "models": trained_models,
        "weights": ensemble_weights,
        "brier_scores": brier_scores,
    }
    ensemble_metrics = {
        "val_brier_score": None,  # Ensemble Brier computed post-blend
        "component_weights": ensemble_weights,
        "component_brier_scores": brier_scores,
    }
    return ensemble_state, ensemble_metrics


def train_pinnacle(conn, config=None):
    """Registry-compliant train: trains Pinnacle-augmented component models, computes weights.

    Same pattern as train() but uses PINNACLE_COMPONENT_MODELS instead of COMPONENT_MODELS.
    No Bayesian component — only logistic_v3_pinnacle and xgboost_v2_pinnacle.
    """
    from src.model import MODEL_REGISTRY
    from src.model.base import build_training_matrix, compute_time_weights, temporal_split

    if config is None:
        config = {}

    X, y, match_dates = build_training_matrix(conn)
    weights = compute_time_weights(match_dates)
    split = temporal_split(X, y, weights, match_dates)

    trained_models = {}
    brier_scores = {}

    for model_key in PINNACLE_COMPONENT_MODELS:
        if model_key not in MODEL_REGISTRY:
            logger.warning("Pinnacle component model %s not in registry, skipping", model_key)
            continue
        try:
            entry = MODEL_REGISTRY[model_key]
            model, metrics = entry["train"](conn, config.get(model_key, {}))
            trained_models[model_key] = {"model": model, "predict": entry["predict"]}
            brier_scores[model_key] = metrics.get("val_brier_score")
            logger.info("Pinnacle ensemble component %s: brier=%.4f",
                       model_key, brier_scores[model_key] or -1)
        except Exception as exc:
            logger.warning("Pinnacle ensemble component %s failed: %s", model_key, exc)
            brier_scores[model_key] = None

    ensemble_weights = compute_weights(brier_scores)

    ensemble_state = {
        "models": trained_models,
        "weights": ensemble_weights,
        "brier_scores": brier_scores,
    }
    ensemble_metrics = {
        "val_brier_score": None,
        "component_weights": ensemble_weights,
        "component_brier_scores": brier_scores,
    }
    return ensemble_state, ensemble_metrics


def predict_pinnacle(ensemble_state, features, **kwargs):
    """Registry-compliant predict for Pinnacle ensemble. Same logic as predict()."""
    return predict(ensemble_state, features, **kwargs)


def predict(ensemble_state, features, **kwargs):
    """Registry-compliant predict: blend component model predictions.

    Parameters
    ----------
    ensemble_state: dict from train() with "models" and "weights"
    features: np.ndarray feature vector

    Returns
    -------
    dict with "calibrated_prob" (blended probability)
    """
    predictions = {}
    for model_key, model_info in ensemble_state["models"].items():
        if model_key not in ensemble_state["weights"]:
            continue  # model excluded from ensemble
        try:
            pred = model_info["predict"](model_info["model"], features)
            if isinstance(pred, dict):
                predictions[model_key] = pred.get("calibrated_prob", pred.get("p50", 0.5))
            else:
                predictions[model_key] = float(pred)
        except Exception as exc:
            logger.warning("Ensemble predict failed for %s: %s", model_key, exc)

    if not predictions:
        return {"calibrated_prob": 0.5}  # fallback

    # Re-normalize weights for available predictions only
    available_weights = {k: ensemble_state["weights"][k]
                        for k in predictions if k in ensemble_state["weights"]}
    total_w = sum(available_weights.values())
    if total_w > 0:
        norm_weights = {k: v / total_w for k, v in available_weights.items()}
    else:
        norm_weights = {k: 1.0 / len(predictions) for k in predictions}

    blended = blend(predictions, norm_weights)
    return {"calibrated_prob": blended}
