---
phase: 07-advanced-models-ensemble
plan: "01"
subsystem: model
tags: [registry, refactor, logistic, schema, migration]
dependency_graph:
  requires: []
  provides:
    - src/model/base.py (LOGISTIC_FEATURES, build_training_matrix, compute_time_weights, temporal_split, save_model, load_model)
    - src/model/logistic.py (train, predict, train_and_calibrate)
    - src/model/__init__.py (MODEL_REGISTRY with logistic_v1)
    - p5/p50/p95 columns in predictions table
  affects:
    - src/model/trainer.py (now a shim)
    - src/model/predictor.py (import path + CI column support)
    - src/db/schema.sql (predictions table extended)
tech_stack:
  added: []
  patterns:
    - Registry pattern for pluggable ML models
    - Backward-compatible shim for zero-touch migration of existing callers
key_files:
  created:
    - src/model/base.py
    - src/model/logistic.py
    - tests/test_model_registry.py
  modified:
    - src/model/trainer.py
    - src/model/__init__.py
    - src/model/predictor.py
    - src/db/schema.sql
decisions:
  - "base.py holds shared utilities; logistic.py holds model-specific logic — clean separation for future model types"
  - "trainer.py becomes a shim (re-exports only) so walk_forward.py, api/main.py, and odds/cli.py require zero import changes"
  - "store_prediction merges defaults {p5:None, p50:None, p95:None} before SQL so legacy test dicts with no CI keys continue to work"
  - "train_and_calibrate kept in logistic.py (not only train()) so walk_forward.py run_fold calling it with pre-split data works unchanged"
metrics:
  duration: "4 minutes"
  completed_date: "2026-03-18"
  tasks_completed: 2
  files_changed: 7
---

# Phase 7 Plan 1: Model Registry Refactor Summary

Registry-based model architecture with base.py shared utilities, logistic.py registry-compliant wrapper, trainer.py backward-compatible shim, MODEL_REGISTRY with logistic_v1, and predictions schema migration for Bayesian credible interval columns.

## What Was Built

Refactored the model layer from a monolithic `trainer.py` into a pluggable registry architecture. All existing callers (walk_forward.py, api/main.py, odds/cli.py) require zero import changes via the trainer.py shim.

### Key components

**src/model/base.py** — New shared utilities module extracted from trainer.py:
- `LOGISTIC_FEATURES` (12-entry list constant)
- `build_training_matrix(conn)` — SQL-driven pairwise differential matrix assembly
- `compute_time_weights(match_dates, half_life_days, reference_date)` — exponential decay weights
- `temporal_split(X, y, weights, match_dates, train_ratio)` — chronological 80/20 split
- `save_model(calibrated_model, path)` / `load_model(path)` — joblib serialization

**src/model/logistic.py** — Registry-compliant logistic regression module:
- `train(conn, config=None)` — registry interface, calls build_training_matrix internally
- `predict(model, features)` — registry interface, returns `{"calibrated_prob": float}`
- `train_and_calibrate(X_train, y_train, X_val, y_val, weights_train)` — backward-compat for walk_forward.py

**src/model/trainer.py** — Converted to a thin re-export shim (no function definitions).

**src/model/__init__.py** — MODEL_REGISTRY added:
```python
MODEL_REGISTRY = {
    "logistic_v1": {"train": logistic_train, "predict": logistic_predict},
}
```

**src/model/predictor.py** — Updated:
- Import `LOGISTIC_FEATURES` from `src.model.base` (direct, not via shim)
- `store_prediction` now includes p5/p50/p95 in INSERT with None defaults for backward compat
- `predict_match` dicts include `"p5": None, "p50": None, "p95": None`

**src/db/schema.sql** — Three nullable columns added to `predictions` table:
```sql
p5   REAL,  -- Bayesian 5th percentile (90% CI lower bound, NULL for non-Bayesian)
p50  REAL,  -- Bayesian 50th percentile (median, NULL for non-Bayesian)
p95  REAL,  -- Bayesian 95th percentile (90% CI upper bound, NULL for non-Bayesian)
```

**tests/test_model_registry.py** — 13 new tests across 4 test classes:
- `TestModelRegistry` — registry structure and callable signatures
- `TestBaseImports` — base.py exports
- `TestTrainerShimBackwardCompat` — trainer.py shim backward compatibility
- `TestSchemaHasCIColumns` — p5/p50/p95 schema column presence and NULL acceptance

## Test Results

```
65 passed in 0.91s
```
- 52 pre-existing tests in test_model.py: all pass
- 13 new tests in test_model_registry.py: all pass

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Schema update pulled into Task 1 to fix store_prediction OperationalError**
- **Found during:** Task 1 verification
- **Issue:** `store_prediction` references p5/p50/p95 columns in INSERT SQL but schema.sql didn't have them yet — causing `sqlite3.OperationalError: table predictions has no column named p5`
- **Fix:** Added p5/p50/p95 columns to schema.sql as part of Task 1 (plan intended this for Task 2, but it is required for tests to pass)
- **Files modified:** src/db/schema.sql
- **Commit:** e0fa681

**2. [Rule 2 - Missing Functionality] store_prediction defaults for CI keys**
- **Found during:** Task 1 verification
- **Issue:** `test_store_prediction_inserts_row` passes a dict without p5/p50/p95 keys — `sqlite3.ProgrammingError: You did not supply a value for binding 15`
- **Fix:** `store_prediction` merges `{"p5": None, "p50": None, "p95": None}` before the INSERT so legacy callers with no CI keys continue to work. Plan already described this as the intended behavior.
- **Files modified:** src/model/predictor.py
- **Commit:** e0fa681

## Commits

| Hash | Message |
|------|---------|
| e0fa681 | feat(07-01): model registry refactor — base.py, logistic.py, trainer.py shim, MODEL_REGISTRY |
| 9b2abe8 | test(07-01): add model registry tests and schema CI column verification |

## Self-Check: PASSED

All created files exist on disk. Both task commits verified in git log.
