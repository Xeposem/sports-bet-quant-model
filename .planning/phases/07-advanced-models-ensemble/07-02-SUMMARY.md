---
phase: 07-advanced-models-ensemble
plan: 02
subsystem: model
tags: [xgboost, optuna, sklearn, calibration, feature-engineering]

# Dependency graph
requires:
  - phase: 07-advanced-models-ensemble/07-01
    provides: base.py shared utilities (LOGISTIC_FEATURES, build_training_matrix, compute_time_weights, temporal_split, save_model, load_model)
  - phase: 03-baseline-model-ev-framework
    provides: CalibratedClassifierCV(FrozenEstimator) calibration pattern, logistic.py model interface pattern

provides:
  - XGB_FEATURES constant (28 pairwise differential features covering all match_features columns)
  - build_xgb_training_matrix(conn, train_end=None) function with optional walk-forward fold boundary
  - src/model/xgboost_model.py with train_fold, train, predict, _objective, save_feature_importance
  - MODEL_REGISTRY["xgboost_v1"] entry with callable train/predict
affects: [07-03, 07-04, 07-05, 08-props-ml, 09-paper-trading]

# Tech tracking
tech-stack:
  added: [xgboost==2.1.4, optuna==4.8.0]
  patterns:
    - Optuna TPESampler hyperparameter search with temporal CV (TimeSeriesSplit) for no future data leakage
    - Dual calibration (CalibratedClassifierCV sigmoid + isotonic) with auto-selection by Brier score
    - Feature importance extraction before calibration wrapping (from XGBClassifier.feature_importances_)
    - Registry-compliant model interface: train(conn, config) and predict(model, features) returning dict

key-files:
  created:
    - src/model/xgboost_model.py
    - tests/test_model_xgboost.py
  modified:
    - src/model/base.py
    - src/model/__init__.py

key-decisions:
  - "XGB_FEATURES has 28 entries (not 27 as plan comment suggested) — plan listed 5 one-hot context features (surface_clay, surface_grass, surface_hard, level_G, level_M) making actual count 12+11+5=28; test updated to reflect reality"
  - "XGBoost uses ALL match_features columns (28 pairwise differentials) per user decision — no manual feature selection, let trees decide"
  - "build_xgb_training_matrix train_end parameter allows same function to serve both registry train() and walk-forward fold calls — avoids SQL duplication"
  - "eval_metric=logloss and verbosity=0 used in XGBClassifier — use_label_encoder removed in XGBoost 1.6"

patterns-established:
  - "Pattern: Optuna study with TPESampler seed=42 on training data only, then retrain on full train split with best params"
  - "Pattern: Pipeline(scaler + XGBClassifier) then FrozenEstimator calibration — same as logistic.py calibration pattern"
  - "Pattern: Feature importance extracted from named_steps['clf'] before calibration wrapping"

requirements-completed: [MOD-02]

# Metrics
duration: 4min
completed: 2026-03-18
---

# Phase 07 Plan 02: XGBoost Model with Optuna Tuning Summary

**XGBoost gradient boosting model with 28-column full match_features feature set, Optuna TPE hyperparameter search, dual Platt/isotonic calibration, and MODEL_REGISTRY xgboost_v1 entry**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-18T21:24:50Z
- **Completed:** 2026-03-18T21:28:50Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- XGB_FEATURES constant (28 features) added to base.py covering all match_features numeric columns plus surface/tourney_level one-hots
- build_xgb_training_matrix(conn, train_end=None) added to base.py with optional temporal fold boundary for walk-forward compatibility
- xgboost_model.py implements train_fold with Optuna TPE search + dual calibration auto-selecting lower Brier score method
- Feature importances extracted as 28-entry dict keyed by XGB_FEATURES names (stored per fold via save_feature_importance)
- MODEL_REGISTRY updated with xgboost_v1 entry; all 90 tests pass across xgboost, registry, and model test suites

## Task Commits

Each task was committed atomically:

1. **Task 1: Add XGB_FEATURES and build_xgb_training_matrix to base.py** - `fd0a456` (feat)
2. **Task 2: Implement XGBoost model with Optuna tuning and dual calibration** - `a3c7d7a` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/model/base.py` - Added XGB_FEATURES (28 features), _BUILD_XGB_MATRIX_SQL, build_xgb_training_matrix()
- `src/model/xgboost_model.py` - Created: _objective(), train_fold(), train(), predict(), save_feature_importance()
- `src/model/__init__.py` - Added xgboost_v1 entry to MODEL_REGISTRY
- `tests/test_model_xgboost.py` - Created: TestXGBFeatures, TestXGBoostTrainFold, TestXGBoostTuning, TestXGBoostImportance, TestXGBoostPredict, TestXGBoostRegistry

## Decisions Made

- XGB_FEATURES count is 28 (not 27 as the plan comment suggested). The plan's feature list explicitly includes 5 one-hot context features (surface_clay, surface_grass, surface_hard, level_G, level_M), making the actual count 12+11+5=28. Test updated to match reality.
- XGBoost uses ALL match_features columns per user decision — pairwise winner-loser differentials for all numeric columns, one-hot encoding for surface and tourney_level.
- build_xgb_training_matrix uses a single SQL constant with string replacement for the optional train_end filter — avoids duplicating SQL for walk-forward use (Plan 04).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected XGB_FEATURES count from 27 to 28 in tests**
- **Found during:** Task 1 (XGB_FEATURES verification)
- **Issue:** Plan comment said "27 features (12 logistic + 11 new numeric + 4 one-hot context)" but the actual XGB_FEATURES list in the plan contained 5 one-hot entries (surface_clay, surface_grass, surface_hard, level_G, level_M), totaling 28. The test assertion `assert len(XGB_FEATURES) == 27` failed.
- **Fix:** Updated test to `assert len(XGB_FEATURES) == 28` with corrected comment. Feature list itself matches the plan spec exactly — the comment in the plan was wrong, not the list.
- **Files modified:** tests/test_model_xgboost.py
- **Verification:** TestXGBFeatures::test_xgb_features_length passes
- **Committed in:** fd0a456 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - incorrect count in plan comment vs actual feature list)
**Impact on plan:** Minor count correction. Feature set, SQL, and model implementation match plan exactly.

## Issues Encountered

None — all dependencies (xgboost 2.1.4, optuna 4.8.0, sklearn FrozenEstimator) were available and working correctly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- xgboost_v1 is registered and callable via MODEL_REGISTRY
- build_xgb_training_matrix(conn, train_end=None) ready for Plan 04 walk-forward multi-model dispatch
- Feature importance storage via save_feature_importance ready for Plan 03 (Bayesian model) comparison
- All 90 model tests pass; existing logistic_v1 regression unaffected

---
*Phase: 07-advanced-models-ensemble*
*Completed: 2026-03-18*

## Self-Check: PASSED

- FOUND: src/model/base.py
- FOUND: src/model/xgboost_model.py
- FOUND: src/model/__init__.py
- FOUND: tests/test_model_xgboost.py
- FOUND: .planning/phases/07-advanced-models-ensemble/07-02-SUMMARY.md
- FOUND commit: fd0a456
- FOUND commit: a3c7d7a
