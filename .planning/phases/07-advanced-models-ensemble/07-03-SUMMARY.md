---
phase: 07-advanced-models-ensemble
plan: 03
subsystem: model
tags: [bayesian, pymc, mcmc, credible-intervals, partial-pooling, model-registry]
dependency_graph:
  requires:
    - 07-01  # base.py, logistic.py, MODEL_REGISTRY foundation, predictor.py p5/p50/p95 columns
  provides:
    - src/model/bayesian.py  # Bayesian hierarchical logistic with PyMC
    - bayesian_v1 registry entry  # in MODEL_REGISTRY
  affects:
    - src/model/__init__.py  # MODEL_REGISTRY updated with bayesian_v1
tech_stack:
  added:
    - pymc==5.12.0  # NUTS sampler, pm.Data containers, pm.set_data, sample_posterior_predictive
    - arviz==0.17.1  # az.summary r_hat convergence, InferenceData format
    - pytensor==2.19.0  # transitive dep of pymc; PyTensor computation backend
    - scipy==1.12.0  # downgraded from 1.13.1 to fix arviz 0.17.1 signal.gaussian import
  patterns:
    - PyMC hierarchical logistic with pm.Data for out-of-sample prediction (pm.set_data pattern)
    - Surface partial pooling: shared hyperpriors (mu_alpha, sigma_alpha) across 3 surface groups
    - Module-level pm import (with try/except) so tests can patch at src.model.bayesian.pm
    - Lazy registry wrappers in __init__.py so MODEL_REGISTRY import does not trigger PyMC load
key_files:
  created:
    - src/model/bayesian.py  # full Bayesian model implementation
    - tests/test_model_bayesian.py  # 21 tests with mocked MCMC
  modified:
    - src/model/__init__.py  # added bayesian_v1 with lazy wrappers + 2 new test methods
    - tests/test_model_registry.py  # added test_registry_contains_bayesian_v1, test_registry_has_three_models
decisions:
  - "pm imported at module level via try/except rather than inside functions — allows @patch(src.model.bayesian.pm) in tests while module still loads without pymc if unavailable"
  - "arviz imported at module level (not lazy) because it is much lighter than pymc and needed for az.summary patchability in tests"
  - "scipy downgraded to <1.13 to fix arviz 0.17.1 incompatibility (scipy.signal.gaussian removed in scipy 1.13)"
  - "Lazy __init__.py wrappers (_lazy_bayesian_train/_lazy_bayesian_predict) prevent PyMC load at MODEL_REGISTRY import time — matches pymc-avoidance pattern from base.py"
metrics:
  duration_minutes: 8
  completed_date: "2026-03-18"
  tasks_completed: 2
  files_created: 2
  files_modified: 2
---

# Phase 7 Plan 3: Bayesian Hierarchical Logistic Model Summary

**One-liner:** PyMC hierarchical logistic with 3-surface partial pooling producing p5/p50/p95 credible intervals registered as bayesian_v1 in MODEL_REGISTRY.

## What Was Built

### src/model/bayesian.py

Bayesian hierarchical logistic regression model using PyMC with:

- `SURFACE_INDEX = {"Hard": 0, "Clay": 1, "Grass": 2}` — module-level constant for consistent surface encoding
- `_surface_str_to_idx(surface_strings)` — converts surface strings to int64 indices (unknown surfaces -> 0)
- `train_fold(X_train, y_train, X_val, y_val, w_train, surface_train, config)` — full MCMC training
  - Standardizes features (stores X_mean, X_std for prediction)
  - Hyperpriors: `mu_alpha ~ Normal(0,1)`, `sigma_alpha ~ HalfNormal(1)` for partial pooling
  - Surface intercepts: `alpha ~ Normal(mu_alpha, sigma_alpha, shape=3)`
  - Global feature weights: `beta ~ Normal(0, 1, shape=n_features)`
  - `pm.Data("X", ...)` and `pm.Data("surface_idx", ...)` for out-of-sample prediction
  - NUTS sampler: configurable draws/tune/chains/target_accept (defaults: 2000/1000/2/0.9)
  - Convergence check: `az.summary(idata)["r_hat"].max()` — warns if > 1.1
  - Returns validation Brier score and log loss using p50 predictions
- `_predict_internal(model, idata, X_new, X_mean, X_std, surface_idx_new)` — pm.set_data + sample_posterior_predictive
- `predict(trained, features, surface_idx)` — registry-compatible, handles 1D/2D features
  - `calibrated_prob = p50` for ensemble compatibility
  - Returns scalar floats for single match, arrays for batch
- `train(conn, config)` — registry-compatible, builds matrix from DB

### src/model/__init__.py (updated)

Added lazy wrappers `_lazy_bayesian_train` and `_lazy_bayesian_predict` that import from `src.model.bayesian` only when called. This ensures `from src.model import MODEL_REGISTRY` does not trigger PyMC/PyTensor import at module load time.

MODEL_REGISTRY now contains: `["logistic_v1", "xgboost_v1", "bayesian_v1"]`

## Tests

**tests/test_model_bayesian.py** — 21 tests, all pass with mocked MCMC:
- `TestSurfaceIndex` (6 tests): SURFACE_INDEX mapping, _surface_str_to_idx, unknown surface fallback
- `TestBayesianTrainFold` (5 tests): returns model/idata/X_mean/X_std, metrics with max_rhat and converged, surface_train=None defaults
- `TestBayesianPredict` (6 tests): p5/p50/p95/calibrated_prob keys, calibrated_prob=p50, scalar floats for single match, arrays for batch, surface_idx handling
- `TestBayesianCI` (3 tests): p5<=p50<=p95 ordering, p50 in unit interval, percentile math correctness
- `TestBayesianRegistry` (1 test): MODEL_REGISTRY contains bayesian_v1 with train and predict callables

**tests/test_model_registry.py** — 2 new tests added:
- `test_registry_contains_bayesian_v1`
- `test_registry_has_three_models`

Total: 38 tests pass (21 bayesian + 17 registry).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] scipy 1.13.1 incompatible with arviz 0.17.1**
- **Found during:** PyMC installation
- **Issue:** `scipy.signal.gaussian` was removed in scipy 1.13; arviz 0.17.1 (the latest Python 3.9 compatible version) imports it at module level
- **Fix:** Downgraded scipy from 1.13.1 to 1.12.0 (`pip install "scipy<1.13"`)
- **Impact:** pymatgen (unrelated dependency) has a >=1.13 requirement but this does not affect our use case
- **Files modified:** environment only (pip install)

**2. [Rule 1 - Bug] pm imported module-level instead of function-level for mock patchability**
- **Found during:** Task 1 GREEN phase — tests failed with `AttributeError: module 'src.model.bayesian' does not have the attribute 'pm'`
- **Issue:** The plan specified `@patch("src.model.bayesian.pm")` in test decorators, but pm was imported inside functions — the patch target `src.model.bayesian.pm` doesn't exist with local imports
- **Fix:** Added `import pymc as pm` at module level via `try/except ImportError` block. The try/except pattern preserves graceful degradation if pymc is not installed, while the module-level binding makes the patch target available
- **Decision:** This slightly changes the import behavior (pm now imports at module load time) but the RESEARCH.md noted "Do NOT import pymc at module level" for `__init__.py` specifically to avoid triggering on `from src.model import MODEL_REGISTRY`. That concern is addressed by the lazy wrappers in `__init__.py`.
- **Files modified:** src/model/bayesian.py (added module-level pm import), src/model/__init__.py (kept lazy wrappers)

## Self-Check: PASSED
