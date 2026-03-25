---
phase: 12-add-pinnacle-odds-as-a-feature-and-retrain-on-the-residual
plan: "03"
subsystem: model
tags: [ensemble, pinnacle, walk-forward, model-registry]
requires: [12-02-SUMMARY.md]
provides: [ensemble_v2_pinnacle train/predict, PINNACLE_COMPONENT_MODELS, walk-forward dispatch]
affects: [src/backtest/walk_forward.py, src/model/__init__.py]
tech-stack:
  added: []
  patterns: [inverse-brier-weighted-ensemble, lazy-function-import]
key-files:
  created: []
  modified:
    - src/model/ensemble.py
    - src/model/__init__.py
    - src/backtest/walk_forward.py
    - tests/test_model_registry.py
decisions:
  - "predict_pinnacle delegates to predict() — ensemble blending is model-agnostic; no duplication needed"
  - "Patch target for train_pinnacle mock tests is src.model.MODEL_REGISTRY (not src.model.ensemble.MODEL_REGISTRY) — function uses local import pattern matching existing ensemble.train()"
metrics:
  duration: 7 minutes
  completed: "2026-03-25T01:56:58Z"
  tasks: 1
  files: 4
---

# Phase 12 Plan 03: Ensemble V2 Pinnacle Summary

Ensemble v2 pinnacle blending logistic_v3_pinnacle + xgboost_v2_pinnacle via inverse Brier score weights, registered in MODEL_REGISTRY and wired into walk-forward fold dispatch.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for ensemble_v2_pinnacle | b84818b | tests/test_model_registry.py |
| 1 (GREEN) | Implement ensemble_v2_pinnacle | bcdd41a | ensemble.py, __init__.py, walk_forward.py, test_model_registry.py |

## What Was Built

### ensemble.py
- Added `PINNACLE_COMPONENT_MODELS = ["logistic_v3_pinnacle", "xgboost_v2_pinnacle"]` constant after `COMPONENT_MODELS`
- Added `train_pinnacle(conn, config=None)` — mirrors `train()` but iterates over `PINNACLE_COMPONENT_MODELS`; no Bayesian component
- Added `predict_pinnacle(ensemble_state, features, **kwargs)` — thin delegate to `predict()` since ensemble blending is model-agnostic

### src/model/__init__.py
- Added import of `train_pinnacle as ensemble_pinnacle_train` and `predict_pinnacle as ensemble_pinnacle_predict` from ensemble module
- Added `"ensemble_v2_pinnacle": {"train": ensemble_pinnacle_train, "predict": ensemble_pinnacle_predict}` to MODEL_REGISTRY
- Registry now has 7 entries: logistic_v1, xgboost_v1, bayesian_v1, ensemble_v1, logistic_v3_pinnacle, xgboost_v2_pinnacle, ensemble_v2_pinnacle

### src/backtest/walk_forward.py
- Added `elif model_version == "ensemble_v2_pinnacle":` branch in `_train_model_for_fold`:
  - Trains logistic_v3_pinnacle using the pre-built 16-column X_train arrays
  - Trains xgboost_v2_pinnacle by calling `build_xgb_training_matrix(conn, train_end)` for 32-column arrays
  - Computes inverse Brier weights and returns ensemble_state dict
- Added `elif model_version == "ensemble_v2_pinnacle":` branch in `_predict_with_model`:
  - Routes logistic_v3_pinnacle to `feature_vec` (16-col)
  - Routes xgboost_v2_pinnacle to `xgb_feature_vec` (32-col, warns+skips if None)
  - Re-normalizes weights for available predictions, delegates to `blend()`

### tests/test_model_registry.py
- Added `TestEnsembleV2Pinnacle` class with 4 tests:
  - `test_ensemble_v2_pinnacle_in_registry`: verifies entry and callables
  - `test_pinnacle_component_models`: asserts PINNACLE_COMPONENT_MODELS list
  - `test_ensemble_v1_unchanged`: asserts COMPONENT_MODELS unchanged
  - `test_ensemble_v2_train_uses_pinnacle_components`: mock-based integration test

## Verification

```
All 7 model versions registered
Component lists OK
588 passed (test_model_bayesian.py excluded: missing arviz dep, pre-existing)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test mock patch target corrected**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Test patched `src.model.ensemble.MODEL_REGISTRY` but `train_pinnacle` uses `from src.model import MODEL_REGISTRY` (local import), so the attribute doesn't exist on the ensemble module
- **Fix:** Changed patch target to `src.model.MODEL_REGISTRY` (the actual registry dict in `__init__.py`)
- **Files modified:** tests/test_model_registry.py
- **Commit:** bcdd41a

**2. [Rule 1 - Bug] Test patch targets for base functions corrected**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Test patched `src.model.ensemble.build_training_matrix` etc. but these are imported inside function body, not at module level
- **Fix:** Changed to `src.model.base.build_training_matrix`, `src.model.base.compute_time_weights`, `src.model.base.temporal_split`
- **Files modified:** tests/test_model_registry.py
- **Commit:** bcdd41a

## Known Stubs

None — all ensemble dispatch paths fully implemented and tested.

## Self-Check: PASSED

- src/model/ensemble.py contains "PINNACLE_COMPONENT_MODELS": YES
- src/model/ensemble.py contains "def train_pinnacle(": YES
- src/model/ensemble.py contains "def predict_pinnacle(": YES
- src/model/__init__.py contains "ensemble_v2_pinnacle": YES
- src/backtest/walk_forward.py contains "ensemble_v2_pinnacle" (both functions): YES
- tests/test_model_registry.py contains "def test_ensemble_v2_pinnacle_in_registry": YES
- tests/test_model_registry.py contains "def test_pinnacle_component_models": YES
- Commits b84818b and bcdd41a exist: YES
