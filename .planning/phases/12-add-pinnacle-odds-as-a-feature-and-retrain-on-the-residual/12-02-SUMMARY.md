---
phase: 12-add-pinnacle-odds-as-a-feature-and-retrain-on-the-residual
plan: "02"
subsystem: model-features
tags: [pinnacle, features, model-registry, walk-forward, tdd]
dependency_graph:
  requires: [12-01]
  provides: [extended-feature-constants, pinnacle-model-versions, walk-forward-dispatch]
  affects: [src/model/base.py, src/model/__init__.py, src/backtest/walk_forward.py]
tech_stack:
  added: []
  patterns: [tdd-red-green, feature-constant-extension, registry-pattern, sql-extension]
key_files:
  created: []
  modified:
    - src/model/base.py
    - src/model/__init__.py
    - src/backtest/walk_forward.py
    - src/model/predictor.py
    - tests/test_model.py
    - tests/test_model_xgboost.py
    - tests/test_model_registry.py
    - tests/test_backtest.py
decisions:
  - "XGB_FEATURES expanded to 32 (not 31 as planned) — original list had 30 entries, plan incorrectly stated 29; 30+2=32 is correct count"
  - "predictor.py _FEATURE_QUERY extended with pinnacle columns — auto-fix Rule 1 (IndexError without it)"
metrics:
  duration: ~15 min
  completed: "2026-03-25"
  tasks: 2
  files_modified: 8
---

# Phase 12 Plan 02: Feature Constants, Registry, and Walk-Forward Pinnacle Extension Summary

Extended LOGISTIC_FEATURES (14->16) and XGB_FEATURES (30->32) with pinnacle_prob_diff and has_no_pinnacle, updated all training SQL with COALESCE imputation, registered logistic_v3_pinnacle and xgboost_v2_pinnacle in MODEL_REGISTRY, and updated walk-forward fold SQL and dispatch routing.

## Tasks Completed

| # | Task | Commit | Status |
|---|------|--------|--------|
| 1 (RED) | Failing tests for feature constants, registry, walk-forward | 7db0264 | Done |
| 1 (GREEN) | Extend base.py, __init__.py, walk_forward.py, predictor.py | 85d752b | Done |
| 2 | Walk-forward SQL and dispatch (included in GREEN commit) | 85d752b | Done |

## What Was Built

### Feature Constants (src/model/base.py)

- `LOGISTIC_FEATURES`: Extended from 14 to 16 entries by appending `pinnacle_prob_diff` and `has_no_pinnacle`
- `XGB_FEATURES`: Extended from 30 to 32 entries with the same two columns
- `_BUILD_MATRIX_SQL`: Added `COALESCE(w.pinnacle_prob_winner, 0.5) - COALESCE(l.pinnacle_prob_winner, 0.5) AS pinnacle_prob_diff` and `CASE WHEN w.pinnacle_prob_winner IS NULL THEN 1 ELSE 0 END AS has_no_pinnacle`
- `_BUILD_XGB_MATRIX_SQL`: Same additions
- `augment_with_flipped`: `has_no_pinnacle` added to `_NON_DIFF_COLS` so it is preserved (not negated) in flipped rows

### Model Registry (src/model/__init__.py)

- `logistic_v3_pinnacle` registered with logistic_train / logistic_predict (same functions; pinnacle included via updated LOGISTIC_FEATURES)
- `xgboost_v2_pinnacle` registered with xgb_train / xgb_predict (same pattern)

### Walk-Forward (src/backtest/walk_forward.py)

- `_FOLD_MATRIX_SQL`: pinnacle columns added before ORDER BY
- `_FOLD_TEST_MATCHES_SQL`: pinnacle columns inserted before `o.decimal_odds_a, o.decimal_odds_b` (feature offsets preserved by LOGISTIC_FEATURES length)
- `_FOLD_XGB_TEST_MATCHES_SQL`: same pattern
- `_train_model_for_fold`: `logistic_v1` branch expanded to `("logistic_v1", "logistic_v3_pinnacle")`, `xgboost_v1` branch expanded to `("xgboost_v1", "xgboost_v2_pinnacle")`
- `_predict_with_model`: same branch expansions
- `run_fold`: XGB feature fetch extended to include `xgboost_v2_pinnacle` and `ensemble_v2_pinnacle`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] predictor.py _FEATURE_QUERY missing pinnacle columns**
- **Found during:** GREEN phase test run
- **Issue:** `_FEATURE_QUERY` in `src/model/predictor.py` returned 14 columns but `LOGISTIC_FEATURES` now has 16; `[row[i + 5] for i in range(len(LOGISTIC_FEATURES))]` caused IndexError
- **Fix:** Added pinnacle columns to `_FEATURE_QUERY` SELECT clause with COALESCE imputation
- **Files modified:** src/model/predictor.py
- **Commit:** 85d752b

**2. [Rule 1 - Bug] Synthetic test data width mismatch**
- **Found during:** GREEN phase test run
- **Issue:** `make_synthetic_data` in test_model.py used 14 columns; `augment_with_flipped` called with LOGISTIC_FEATURES (16) caused IndexError on has_no_pinnacle index
- **Fix:** Updated test helper to produce 16-column data. Same fix for test_model_xgboost.py (30->32)
- **Files modified:** tests/test_model.py, tests/test_model_xgboost.py
- **Commit:** 85d752b

**3. [Rule 1 - Arithmetic] XGB_FEATURES count is 32 not 31**
- **Found during:** GREEN phase assertion failure
- **Issue:** Plan stated "29 original + 2 = 31" but original XGB_FEATURES actually had 30 entries; 30+2=32
- **Fix:** Updated test assertion from `== 31` to `== 32` to match reality
- **Files modified:** tests/test_model_xgboost.py
- **Commit:** 85d752b

## Known Stubs

None — all pinnacle features use COALESCE imputation (0.5 differential, has_no_pinnacle=1) for matches without Pinnacle odds, which is the correct production behavior.

## Self-Check: PASSED

- FOUND: src/model/base.py
- FOUND: src/model/__init__.py
- FOUND: src/backtest/walk_forward.py
- FOUND commit: 85d752b (feat)
- FOUND commit: 7db0264 (test)
- All 126 tests pass (test_model + test_model_xgboost + test_model_registry + test_backtest)
