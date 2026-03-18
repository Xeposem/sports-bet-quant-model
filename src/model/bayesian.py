"""Bayesian hierarchical logistic model with PyMC -- surface partial pooling.

Architecture:
  - Hierarchical logistic regression with 3 surface-specific intercepts (partial pooling)
  - Surface groups: Hard (0), Clay (1), Grass (2)
  - Partial pooling via hyperpriors (mu_alpha, sigma_alpha) avoids overfitting on thin
    surface slices (especially grass)
  - Feature weights (beta) are global across surfaces
  - NUTS sampler with configurable draws/tune/chains (defaults: 2000/1000/2)
  - pm.Data containers enable out-of-sample prediction via pm.set_data without re-sampling
  - Output: p5/p50/p95 (90% credible interval) + calibrated_prob (= p50)
  - Convergence checked via az.summary r_hat; warning logged if > 1.1

Key exports:
  - SURFACE_INDEX: module-level constant {"Hard": 0, "Clay": 1, "Grass": 2}
  - train_fold(X_train, y_train, X_val, y_val, w_train, surface_train, config) -> dict
  - predict(trained, features, surface_idx) -> dict with p5/p50/p95/calibrated_prob
  - train(conn, config) -> (trained_dict, metrics)

Note: pymc is imported inside functions (not at module level) to avoid the ~2-3s
PyTensor compilation overhead at import time.
"""
from __future__ import annotations

import logging
import numpy as np

import arviz as az

# pm is imported lazily (inside functions) to avoid the ~2-3s PyTensor compilation
# at module load time. A module-level reference is kept so tests can patch it via
# `@patch("src.model.bayesian.pm")`.
try:
    import pymc as pm
except ImportError:  # pragma: no cover
    pm = None  # type: ignore[assignment]

from src.model.base import (
    build_training_matrix,
    compute_time_weights,
    temporal_split,
    LOGISTIC_FEATURES,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Surface encoding constant
# ---------------------------------------------------------------------------

SURFACE_INDEX = {"Hard": 0, "Clay": 1, "Grass": 2}
"""Mapping from surface string to integer index for partial pooling.

Unknown or NULL surfaces default to 0 (Hard) — the surface with the most data.
"""


def _surface_str_to_idx(surface_strings) -> np.ndarray:
    """Convert iterable of surface strings to integer index array.

    Unknown surfaces (e.g., Carpet, Indoor, None) map to 0 (Hard) as a safe fallback.

    Parameters
    ----------
    surface_strings:
        Iterable of strings, e.g. ["Hard", "Clay", "Grass", "Unknown"]

    Returns
    -------
    np.ndarray of dtype int64
    """
    return np.array([SURFACE_INDEX.get(s, 0) for s in surface_strings], dtype=np.int64)


# ---------------------------------------------------------------------------
# Internal prediction helper
# ---------------------------------------------------------------------------


def _predict_internal(model, idata, X_new, X_mean, X_std, surface_idx_new) -> dict:
    """Internal prediction using pm.set_data + sample_posterior_predictive.

    Parameters
    ----------
    model:
        Trained PyMC model with pm.Data containers "X" and "surface_idx"
    idata:
        InferenceData from pm.sample
    X_new:
        Feature matrix of shape (n_matches, n_features), unscaled
    X_mean, X_std:
        Training set statistics for standardization
    surface_idx_new:
        Integer array of shape (n_matches,) with surface indices

    Returns
    -------
    dict with keys: "p5", "p50", "p95" — numpy arrays of shape (n_matches,)
    """
    X_scaled = (X_new - X_mean) / X_std

    with model:
        pm.set_data({"X": X_scaled, "surface_idx": surface_idx_new})
        ppc = pm.sample_posterior_predictive(
            idata, var_names=["p"], progressbar=False,
        )

    # Extract posterior predictive samples for p
    # Shape: (chains, draws, n_matches)
    p_samples = ppc.posterior_predictive["p"].values
    # Flatten to (chains*draws, n_matches)
    p_flat = p_samples.reshape(-1, p_samples.shape[-1])

    p5 = np.percentile(p_flat, 5, axis=0)
    p50 = np.percentile(p_flat, 50, axis=0)
    p95 = np.percentile(p_flat, 95, axis=0)

    return {"p5": p5, "p50": p50, "p95": p95}


# ---------------------------------------------------------------------------
# train_fold — registry-compatible fold training
# ---------------------------------------------------------------------------


def train_fold(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    w_train: np.ndarray,
    surface_train=None,
    config=None,
) -> dict:
    """Train Bayesian hierarchical logistic on pre-split fold data.

    Parameters
    ----------
    X_train, y_train:
        Training features (n_train, n_features) and labels (n_train,)
    X_val, y_val:
        Validation features and labels for Brier score computation
    w_train:
        Sample weights — accepted for interface compatibility but not used by PyMC
        (NUTS uses the full likelihood; time-decay weighting is not supported by
        PyMC without custom likelihood modifications)
    surface_train:
        Integer array of surface indices (0=Hard, 1=Clay, 2=Grass) for training rows.
        If None, defaults to np.zeros(n_train) — all treated as Hard.
    config:
        Optional dict with keys:
          - draws (int, default 2000): NUTS posterior draws per chain
          - tune (int, default 1000): NUTS tuning steps per chain
          - chains (int, default 2): number of parallel chains
          - target_accept (float, default 0.9): target acceptance rate

    Returns
    -------
    dict with keys:
        "model": PyMC model object
        "idata": ArviZ InferenceData from pm.sample
        "X_mean": ndarray of shape (n_features,) — training feature means
        "X_std": ndarray of shape (n_features,) — training feature stds
        "metrics": dict with max_rhat, converged, val_brier_score, val_log_loss
    """
    if config is None:
        config = {}
    draws = config.get("draws", 2000)
    tune = config.get("tune", 1000)
    chains = config.get("chains", 2)
    target_accept = config.get("target_accept", 0.9)

    if surface_train is None:
        surface_train = np.zeros(len(y_train), dtype=np.int64)

    # Standardize features for better MCMC convergence
    X_mean = X_train.mean(axis=0)
    X_std = X_train.std(axis=0)
    X_std[X_std == 0] = 1.0  # avoid division by zero for constant columns
    X_scaled = (X_train - X_mean) / X_std

    with pm.Model() as model:
        X_data = pm.Data("X", X_scaled)
        surf_data = pm.Data("surface_idx", surface_train)

        # Hyperpriors for partial pooling across surfaces
        mu_alpha = pm.Normal("mu_alpha", 0, 1)
        sigma_alpha = pm.HalfNormal("sigma_alpha", 1)

        # Surface-specific intercepts (partial pooling)
        alpha = pm.Normal("alpha", mu=mu_alpha, sigma=sigma_alpha, shape=3)

        # Global feature weights (shared across surfaces)
        beta = pm.Normal("beta", 0, 1, shape=X_train.shape[1])

        # Logistic link function
        logit_p = alpha[surf_data] + pm.math.dot(X_data, beta)
        p = pm.Deterministic("p", pm.math.sigmoid(logit_p))

        # Bernoulli likelihood
        obs = pm.Bernoulli("obs", p=p, observed=y_train)  # noqa: F841

        idata = pm.sample(
            draws=draws,
            tune=tune,
            chains=chains,
            target_accept=target_accept,
            progressbar=False,
            random_seed=42,
        )

    # Convergence check via R-hat
    summary = az.summary(idata, var_names=["alpha", "beta"])
    max_rhat = float(summary["r_hat"].max())
    converged = max_rhat < 1.1

    if not converged:
        logger.warning("Bayesian fold convergence warning: max r_hat=%.3f", max_rhat)
    else:
        logger.info("Bayesian fold converged: max r_hat=%.3f", max_rhat)

    # Compute validation metrics using p50 predictions
    val_surface_idx = np.zeros(len(y_val), dtype=np.int64)
    val_preds = _predict_internal(model, idata, X_val, X_mean, X_std, val_surface_idx)

    from sklearn.metrics import brier_score_loss, log_loss
    val_brier = float(brier_score_loss(y_val, val_preds["p50"]))
    val_logloss = float(log_loss(y_val, np.clip(val_preds["p50"], 1e-15, 1 - 1e-15)))

    metrics = {
        "max_rhat": max_rhat,
        "converged": converged,
        "val_brier_score": val_brier,
        "val_log_loss": val_logloss,
    }

    return {
        "model": model,
        "idata": idata,
        "X_mean": X_mean,
        "X_std": X_std,
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# predict — registry-compatible prediction
# ---------------------------------------------------------------------------


def predict(trained: dict, features: np.ndarray, surface_idx=None) -> dict:
    """Registry-compliant predict for Bayesian model.

    Parameters
    ----------
    trained:
        Dict returned by train_fold with keys: model, idata, X_mean, X_std
    features:
        numpy array of shape (n_features,) for single match, or (n_matches, n_features)
        for batch prediction
    surface_idx:
        Surface index(es) for prediction.
        - None: defaults to 0 (Hard) for all matches
        - int: same surface for all matches
        - ndarray: per-match surface indices

    Returns
    -------
    For single match (features.ndim == 1 or shape (1, n)):
        dict with float values: p5, p50, p95, calibrated_prob (= p50)
    For batch (n > 1):
        dict with ndarray values: p5, p50, p95, calibrated_prob (= p50)
    """
    if features.ndim == 1:
        features = features.reshape(1, -1)

    n_matches = features.shape[0]

    if surface_idx is None:
        surface_idx = np.zeros(n_matches, dtype=np.int64)
    elif isinstance(surface_idx, (int, np.integer)):
        surface_idx = np.array([surface_idx], dtype=np.int64)

    result = _predict_internal(
        trained["model"],
        trained["idata"],
        features,
        trained["X_mean"],
        trained["X_std"],
        surface_idx,
    )

    # For single-match prediction, return scalar floats
    if n_matches == 1:
        return {
            "p5": float(result["p5"][0]),
            "p50": float(result["p50"][0]),
            "p95": float(result["p95"][0]),
            "calibrated_prob": float(result["p50"][0]),
        }

    return {
        "p5": result["p5"],
        "p50": result["p50"],
        "p95": result["p95"],
        "calibrated_prob": result["p50"],
    }


# ---------------------------------------------------------------------------
# train — registry-compatible full training from DB connection
# ---------------------------------------------------------------------------


def train(conn, config=None):
    """Registry-compliant train: builds matrix from DB, trains Bayesian model.

    Parameters
    ----------
    conn:
        Open SQLite connection with match_features and matches tables populated
    config:
        Optional dict with MCMC configuration (draws, tune, chains, target_accept)

    Returns
    -------
    (trained_dict, metrics_dict) — metrics dict popped from trained_dict
    """
    if config is None:
        config = {}
    X, y, match_dates = build_training_matrix(conn)
    weights = compute_time_weights(match_dates)
    split = temporal_split(X, y, weights, match_dates)
    trained = train_fold(
        split["X_train"],
        split["y_train"],
        split["X_val"],
        split["y_val"],
        split["w_train"],
        config=config,
    )
    metrics = trained.pop("metrics")
    return trained, metrics


# ---------------------------------------------------------------------------
# Serialization (ArviZ NetCDF — not joblib)
# ---------------------------------------------------------------------------


def save_bayesian_model(trained: dict, path: str) -> None:
    """Save Bayesian model idata to NetCDF format.

    Note: Use this instead of joblib for PyMC models. The idata (InferenceData)
    object contains PyTensor-backed arrays that cannot be pickled by joblib.
    The PyMC Model object itself cannot be serialized — must be reconstructed.
    """
    trained["idata"].to_netcdf(path)
    logger.info("Saved Bayesian idata to %s", path)
