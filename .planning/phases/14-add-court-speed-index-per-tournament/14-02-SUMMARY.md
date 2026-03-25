---
phase: 14-add-court-speed-index-per-tournament
plan: "02"
subsystem: models
tags: [court-speed, csi, model-versioning, walk-forward, feature-constants]
dependency_graph:
  requires:
    - src/model/base.py (LOGISTIC_FEATURES, XGB_FEATURES, build_xgb_training_matrix)
    - src/model/__init__.py (MODEL_REGISTRY)
    - src/model/ensemble.py (train_pinnacle, predict_pinnacle)
    - src/backtest/walk_forward.py (_FOLD_MATRIX_SQL, _FOLD_XGB_TEST_MATCHES_SQL)
    - src/features/court_speed.py (court_speed_index table — from Plan 01)
  provides:
    - LOGISTIC_V4_FEATURES (19 entries incl. 3 CSI features)
    - XGB_V3_FEATURES (35 entries incl. 3 CSI features)
    - logistic_v4, xgboost_v3, ensemble_v3 in MODEL_REGISTRY
    - _FOLD_V4_MATRIX_SQL, _FOLD_V4_TEST_MATCHES_SQL, _FOLD_V4_XGB_TEST_MATCHES_SQL
    - build_fold_v4_test_matches, build_fold_v4_xgb_test_matches
    - build_v4_training_matrix, build_v4_xgb_training_matrix
  affects:
    - src/model/base.py (new constants + SQL + builders added)
    - src/model/__init__.py (3 new registry entries)
    - src/model/ensemble.py (train_v3, predict_v3 added)
    - src/backtest/walk_forward.py (new SQL, functions, dispatch)
tech_stack:
  added: []
  patterns:
    - New model version constants extend old via list concatenation (not in-place mutation)
    - has_no_csi=1 fallback indicator mirrors has_no_elo / has_no_pinnacle pattern
    - LEFT JOIN court_speed_index + surface_avg subquery for CSI fallback in SQL
    - Walk-forward dispatch pattern extended for v4/v3: conn+train_end required
    - ensemble_v3 blends logistic_v4 + xgboost_v3 via inverse Brier (same as v2_pinnacle)
key_files:
  created: []
  modified:
    - src/model/base.py
    - src/model/__init__.py
    - src/model/ensemble.py
    - src/backtest/walk_forward.py
decisions:
  - "LOGISTIC_V4_FEATURES = LOGISTIC_FEATURES + [...] — list concatenation preserves old constant intact (serialized models safe)"
  - "XGB_V3_FEATURES = XGB_FEATURES + [...] — same pattern, no in-place mutation"
  - "build_v4_training_matrix accepts optional train_end for walk-forward fold reuse"
  - "ensemble_v3 blends logistic_v4 + xgboost_v3 only (no Bayesian) — follows pinnacle ensemble pattern"
  - "run_fold uses build_fold_v4_test_matches for logistic_v4/ensemble_v3 (19-col feature vec)"
  - "pinnacle_prob_market included in v4 test SQL for CLV computation continuity"
metrics:
  duration_seconds: 360
  completed_date: "2026-03-25"
  tasks_completed: 2
  files_changed: 4
---

# Phase 14 Plan 02: CSI Feature Constants, Model Registry, and Walk-Forward Extension Summary

New model versions logistic_v4 (19 features), xgboost_v3 (35 features), and ensemble_v3 registered in MODEL_REGISTRY; walk-forward SQL and dispatch extended with court_speed_index JOIN for v4/v3 versions; old model versions (v1, v3_pinnacle, v2_pinnacle) completely unchanged.

## What Was Built

### Task 1: Add CSI feature lists and SQL templates to base.py

- Added `LOGISTIC_V4_FEATURES` (19 entries) as `LOGISTIC_FEATURES + 3 CSI` via list concatenation — does NOT modify the original 16-entry constant
- Added `XGB_V3_FEATURES` (35 entries) as `XGB_FEATURES + 3 CSI` — does NOT modify the original 32-entry constant
- CSI features added: `court_speed_index` (raw venue CSI), `has_no_csi` (indicator), `speed_affinity_diff` (winner - loser)
- Added `_BUILD_V4_MATRIX_SQL` — copy of `_BUILD_MATRIX_SQL` extended with CSI columns and two LEFT JOINs: `court_speed_index csi` and a `surface_avg` subquery for fallback
- Added `_BUILD_V4_XGB_MATRIX_SQL` — same pattern for XGBoost
- Added `build_v4_training_matrix(conn, train_end=None)` — uses v4 SQL + LOGISTIC_V4_FEATURES
- Added `build_v4_xgb_training_matrix(conn, train_end=None)` — uses v4 XGB SQL + XGB_V3_FEATURES

### Task 2: Register CSI model versions and extend walk-forward dispatch

**src/model/ensemble.py:**
- Added `CSI_COMPONENT_MODELS = ["logistic_v4", "xgboost_v3"]`
- Added `train_v3(conn, config)` — same pattern as `train_pinnacle` but blends logistic_v4 + xgboost_v3
- Added `predict_v3(ensemble_state, features, **kwargs)` — delegates to `predict()`

**src/model/__init__.py:**
- Added `train_v3 as ensemble_v3_train, predict_v3 as ensemble_v3_predict` imports
- Added 3 new entries to `MODEL_REGISTRY`: `logistic_v4`, `xgboost_v3`, `ensemble_v3`

**src/backtest/walk_forward.py:**
- Added imports: `build_v4_training_matrix`, `build_v4_xgb_training_matrix`, `LOGISTIC_V4_FEATURES`, `XGB_V3_FEATURES`
- Added `_FOLD_V4_MATRIX_SQL` — v4 training matrix SQL with CSI JOINs and `:train_end` filter
- Added `_FOLD_V4_TEST_MATCHES_SQL` — v4 test SQL with 19 feature columns + `pinnacle_prob_market` extra column
- Added `_FOLD_V4_XGB_TEST_MATCHES_SQL` — v3 XGB test SQL with 35 feature columns + `pinnacle_prob_market`
- Added `build_fold_v4_test_matches(conn, test_start, test_end)` — returns 19-col feature dicts
- Added `build_fold_v4_xgb_test_matches(conn, test_start, test_end)` — returns 35-col feature dicts
- Extended `_train_model_for_fold` dispatch: `logistic_v4` builds via `build_v4_training_matrix`; `xgboost_v3` via `build_v4_xgb_training_matrix`; `ensemble_v3` trains both sub-models with their correct CSI matrices
- Extended `_predict_with_model` to include `logistic_v4` in logistic branch, `xgboost_v3` in XGB branch, and a new `ensemble_v3` branch
- Updated `run_fold` to use `build_fold_v4_test_matches` for `logistic_v4`/`ensemble_v3` and `build_fold_v4_xgb_test_matches` for `xgboost_v3`/`ensemble_v3`
- Updated `xgb_feature_vec` fetch condition to include `xgboost_v3` and `ensemble_v3`

## Test Results

- `tests/test_model_registry.py`: 22 tests, all passing
- Overall suite (excluding bayesian): 105 passed (1 pre-existing failure from Phase 14-01 table count)

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

One pre-existing test failure noted during test run: `tests/test_backtest.py::TestBacktestSchema::test_table_count_includes_backtest_tables` expects 20 tables but now 21 exist (the `court_speed_index` table was added in Plan 14-01). This is a pre-existing issue, not caused by this plan's changes.

## Known Stubs

None — all feature constants and dispatch functions are fully wired. No hardcoded empty values that would flow to UI rendering.

## Self-Check: PASSED

- `src/model/base.py` contains `LOGISTIC_V4_FEATURES` — FOUND
- `src/model/base.py` contains `XGB_V3_FEATURES` — FOUND
- `src/model/base.py` contains `_BUILD_V4_MATRIX_SQL` — FOUND
- `src/model/base.py` contains `build_v4_training_matrix` — FOUND
- `src/model/__init__.py` contains `logistic_v4` in MODEL_REGISTRY — FOUND
- `src/model/__init__.py` contains `ensemble_v3` in MODEL_REGISTRY — FOUND
- `src/model/ensemble.py` contains `train_v3` — FOUND
- `src/backtest/walk_forward.py` contains `_FOLD_V4_MATRIX_SQL` — FOUND
- `src/backtest/walk_forward.py` contains `LOGISTIC_V4_FEATURES` import — FOUND
- Commit 109ddd8 — FOUND
- Commit 4a34ede — FOUND
