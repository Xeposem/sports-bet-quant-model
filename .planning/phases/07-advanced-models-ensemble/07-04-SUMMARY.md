---
phase: 07-advanced-models-ensemble
plan: "04"
subsystem: model-ensemble
tags: [ensemble, walk-forward, multi-model, xgboost, bayesian, logistic]
dependency_graph:
  requires: ["07-01", "07-02", "07-03"]
  provides: ["ensemble_v1 in MODEL_REGISTRY", "multi-model walk-forward dispatch"]
  affects: ["src/model/__init__.py", "src/backtest/walk_forward.py"]
tech_stack:
  added: []
  patterns:
    - "Inverse Brier score weighting for ensemble blending"
    - "Model dispatch via model_version string in walk-forward"
    - "Dual data path: 12-col logistic features vs 28-col XGB features"
key_files:
  created:
    - src/model/ensemble.py
    - tests/test_ensemble.py
    - tests/test_walk_forward_multimodel.py
  modified:
    - src/model/__init__.py
    - src/backtest/walk_forward.py
decisions:
  - "ensemble_v1 registered in MODEL_REGISTRY with lazy component model dispatch"
  - "XGB test prediction uses build_fold_xgb_test_matches (28-col), not build_fold_test_matches (12-col)"
  - "_FOLD_XGB_TEST_MATCHES_SQL mirrors _BUILD_XGB_MATRIX_SQL column order for correct feature indexing"
  - "Duplicate compute_time_weights/temporal_split imports from base and trainer kept — trainer is a shim, no conflict"
metrics:
  duration_minutes: 4
  completed_date: "2026-03-18"
  tasks_completed: 2
  files_created: 3
  files_modified: 2
requirements_satisfied: [MOD-04]
---

# Phase 07 Plan 04: Ensemble Blending and Multi-Model Walk-Forward Summary

Ensemble blending with inverse Brier score weighting plus walk-forward multi-model dispatch with correct 12-column (logistic/bayesian) vs 28-column (XGBoost) feature dimension routing.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Implement ensemble weight computation and blending | 41c85d2 | src/model/ensemble.py, tests/test_ensemble.py, src/model/__init__.py |
| 2 | Extend walk_forward.py for multi-model support | 5a719a6 | src/backtest/walk_forward.py, tests/test_walk_forward_multimodel.py |

## What Was Built

### Task 1: Ensemble

`src/model/ensemble.py` provides:
- `compute_weights(brier_scores)`: inverse Brier score normalization, filters None/zero Brier models, raises ValueError if all invalid
- `blend(predictions, weights)`: weighted probability average
- `train(conn, config)`: registry-compliant trainer that trains all COMPONENT_MODELS and returns ensemble_state
- `predict(ensemble_state, features)`: blends component predictions with re-normalization for degraded models

`COMPONENT_MODELS = ["logistic_v1", "xgboost_v1", "bayesian_v1"]` — adding a new model requires only this list + registry entry.

`src/model/__init__.py` updated with `"ensemble_v1": {"train": ensemble_train, "predict": ensemble_predict}` as the 4th registry entry.

### Task 2: Multi-Model Walk-Forward

`src/backtest/walk_forward.py` additions:

- `_FOLD_XGB_TEST_MATCHES_SQL`: mirrors `_BUILD_XGB_MATRIX_SQL` column order for test windows, selects all 28 XGB_FEATURES columns
- `build_fold_xgb_test_matches(conn, test_start, test_end)`: fetches 28-column feature vectors for XGBoost prediction
- `_train_model_for_fold(model_version, ...)`: dispatch by model_version
  - logistic_v1: uses pre-built 12-column arrays via `train_and_calibrate`
  - xgboost_v1: ignores pre-built arrays, calls `build_xgb_training_matrix(conn, train_end)` for 28-column arrays
  - bayesian_v1: uses pre-built 12-column arrays via `bayes_train_fold`
  - ensemble_v1: trains each component with its correct feature dimensions
- `_predict_with_model(model_version, model_or_state, feature_vec, xgb_feature_vec=None)`: dispatch by model_version, xgboost_v1 raises ValueError without xgb_feature_vec
- `run_fold` updated: uses `_train_model_for_fold` at Step 4, fetches `xgb_test_matches` lookup for XGBoost/ensemble models, uses `_predict_with_model` for all predictions

## Test Coverage

- `tests/test_ensemble.py`: 12 tests — compute_weights (sum=1, lower Brier = higher weight, None filtering, single model, raises on all-None), blend (weighted avg, equal weights, passthrough), EV integration, registry entries
- `tests/test_walk_forward_multimodel.py`: 10 tests — logistic dispatch, XGBoost calls build_xgb_training_matrix, XGBoost raises without conn, unknown model_version raises, logistic predict float in [0,1], XGBoost predict with 28-col features, XGBoost raises without xgb_feature_vec, ensemble predict returns float, unknown predict raises, XGBoost predict_proba called with 28-col vector not 12-col

**Total: 89 tests pass (all existing + 22 new)**

## Deviations from Plan

**1. [Rule 1 - Feature count] XGB_FEATURES has 28 columns, not 27**
- **Found during:** Task 2 implementation
- **Issue:** Plan references "27-column XGB_FEATURES" throughout but STATE.md already documents this as 28 entries. XGB_FEATURES list in base.py has 28 entries.
- **Fix:** Used `len(XGB_FEATURES)` everywhere instead of hardcoding 27 — dynamic sizing handles any count
- **Files modified:** src/backtest/walk_forward.py, tests/test_walk_forward_multimodel.py
- **Impact:** None — correct feature count used throughout

## Self-Check

All created files exist:
- src/model/ensemble.py: FOUND
- src/model/__init__.py: MODIFIED
- src/backtest/walk_forward.py: MODIFIED
- tests/test_ensemble.py: FOUND
- tests/test_walk_forward_multimodel.py: FOUND

Commits verified:
- 41c85d2: feat(07-04): implement ensemble weight computation and blending
- 5a719a6: feat(07-04): extend walk_forward.py for multi-model support with correct feature dimensions

## Self-Check: PASSED
