---
phase: 07-advanced-models-ensemble
verified: 2026-03-18T00:00:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
gaps: []
---

# Phase 7: Advanced Models and Ensemble Verification Report

**Phase Goal:** GBM and Bayesian models are trained and validated, and a weighted ensemble replaces the single logistic regression baseline as the primary prediction source
**Verified:** 2026-03-18
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | MODEL_REGISTRY contains all four models: logistic_v1, xgboost_v1, bayesian_v1, ensemble_v1 | VERIFIED | `src/model/__init__.py` lines 23-28; `python -c "from src.model import MODEL_REGISTRY; print(sorted(MODEL_REGISTRY.keys()))"` → `['bayesian_v1', 'ensemble_v1', 'logistic_v1', 'xgboost_v1']` |
| 2 | XGBoost model trains on full 28-column feature set with Optuna tuning and dual calibration | VERIFIED | `src/model/xgboost_model.py`: `_objective`, `train_fold`, `CalibratedClassifierCV(FrozenEstimator(...))` — imports `XGB_FEATURES` (28 entries verified), `build_xgb_training_matrix` |
| 3 | Bayesian model produces p5/p50/p95 credible intervals with surface partial pooling | VERIFIED | `src/model/bayesian.py`: `SURFACE_INDEX = {"Hard": 0, "Clay": 1, "Grass": 2}`, `pm.Normal("alpha", ..., shape=3)`, `_predict_internal` returns `{p5, p50, p95}` arrays via `np.percentile` |
| 4 | Ensemble blends component models weighted by inverse Brier score | VERIFIED | `src/model/ensemble.py`: `compute_weights` uses `1.0 / v` inverse weighting, `blend` returns weighted sum; tested: `compute_weights({"a": 0.20, "b": 0.25})` → `{'a': 0.556, 'b': 0.444}` |
| 5 | Ensemble degrades gracefully when a component model fails | VERIFIED | `ensemble.py` line 82-84: `except Exception` sets `brier_scores[model_key] = None`; `compute_weights` filters None values; re-normalizes available weights on predict |
| 6 | Walk-forward engine dispatches per model_version with correct feature dimensions (28-col XGB vs 12-col logistic/bayesian) | VERIFIED | `walk_forward.py`: `_train_model_for_fold` has `xgboost_v1` branch calling `build_xgb_training_matrix(conn, train_end)`; `_predict_with_model` requires `xgb_feature_vec` for `xgboost_v1`; `run_fold` fetches `xgb_test_matches` lookup and passes `xgb_feature_vec` |
| 7 | Ensemble output feeds into compute_ev as `calibrated_prob` without modification | VERIFIED | `ensemble.predict` returns `{"calibrated_prob": blended}` — same dict key as logistic/xgboost; `TestEnsembleEVIntegration::test_ensemble_prob_works_with_compute_ev` confirms no signature change |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/model/base.py` | Shared utilities: 12 LOGISTIC_FEATURES, build_training_matrix, compute_time_weights, temporal_split, save_model, load_model; plus XGB_FEATURES (28), build_xgb_training_matrix | VERIFIED | All 6 shared functions present; XGB_FEATURES has 28 entries (12 logistic + 11 numeric diffs + 5 one-hot context); `build_xgb_training_matrix(conn, train_end=None)` confirmed |
| `src/model/logistic.py` | Registry-compliant train(conn, config)/predict(model, features) + backward-compat train_and_calibrate | VERIFIED | All 3 functions present; `predict` returns `{"calibrated_prob": float}`; trainer.py shim re-exports confirmed |
| `src/model/__init__.py` | MODEL_REGISTRY with all 4 entries | VERIFIED | 4 entries: logistic_v1, xgboost_v1, bayesian_v1 (lazy), ensemble_v1 |
| `src/model/xgboost_model.py` | train_fold, train, predict, _objective, Optuna, dual calibration, feature importances | VERIFIED | All functions present; uses `build_xgb_training_matrix` (not logistic `build_training_matrix`); `CalibratedClassifierCV(FrozenEstimator(...))` both sigmoid and isotonic; feature_importances keyed by XGB_FEATURES names |
| `src/model/bayesian.py` | train_fold, train, predict, SURFACE_INDEX, pm.Data, pm.set_data, pm.sample_posterior_predictive | VERIFIED | All present; `SURFACE_INDEX = {"Hard": 0, "Clay": 1, "Grass": 2}`; `pm.Data("X", ...)` and `pm.set_data` for out-of-sample; convergence check via `az.summary r_hat` |
| `src/model/ensemble.py` | compute_weights, blend, train, predict, COMPONENT_MODELS list | VERIFIED | All present; `COMPONENT_MODELS = ["logistic_v1", "xgboost_v1", "bayesian_v1"]` |
| `src/backtest/walk_forward.py` | _train_model_for_fold, _predict_with_model, build_fold_xgb_test_matches, _FOLD_XGB_TEST_MATCHES_SQL | VERIFIED | All 4 additions confirmed; run_fold updated to use dispatch functions and XGB feature lookup |
| `src/db/schema.sql` | predictions table with p5, p50, p95 REAL nullable columns | VERIFIED | Lines 246-248; `p5 REAL`, `p50 REAL`, `p95 REAL` with NULL-for-non-Bayesian comments |
| `tests/test_model_registry.py` | Registry structure tests, shim backward compat, schema CI columns | VERIFIED | 4 test classes: TestModelRegistry, TestBaseImports, TestTrainerShimBackwardCompat, TestSchemaHasCIColumns |
| `tests/test_model_xgboost.py` | XGB features, train_fold, tuning, importance, predict, registry | VERIFIED | 6 test classes covering all acceptance criteria |
| `tests/test_model_bayesian.py` | SURFACE_INDEX, train_fold, predict, CI ordering, registry | VERIFIED | 5 test classes with mocked MCMC |
| `tests/test_ensemble.py` | compute_weights, blend, EV integration, registry entries | VERIFIED | TestComputeWeights, TestBlend, TestEnsembleEVIntegration, TestEnsembleRegistry |
| `tests/test_walk_forward_multimodel.py` | Multi-model dispatch, XGB 28-col, ValueError without conn/xgb_feature_vec | VERIFIED | 10 tests covering all key dispatch scenarios |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `src/model/logistic.py` | `src/model/base.py` | `from src.model.base import build_training_matrix, compute_time_weights, temporal_split, LOGISTIC_FEATURES` | WIRED | Lines 24-29 confirmed |
| `src/model/trainer.py` | `src/model/base.py` + `src/model/logistic.py` | Re-export shim | WIRED | Lines 13-21; `from src.model.base import ...` and `from src.model.logistic import train_and_calibrate`; `python -c "from src.model.trainer import ... print('shim OK')"` passes |
| `src/model/xgboost_model.py` | `src/model/base.py` | `from src.model.base import build_xgb_training_matrix, XGB_FEATURES, compute_time_weights, temporal_split` | WIRED | Lines 23-29; does NOT import `build_training_matrix` or `LOGISTIC_FEATURES` (correct) |
| `src/model/__init__.py` | `src/model/xgboost_model.py` | `MODEL_REGISTRY["xgboost_v1"]` | WIRED | Line 26: `"xgboost_v1": {"train": xgb_train, "predict": xgb_predict}` |
| `src/model/bayesian.py` | `src/model/base.py` | `from src.model.base import build_training_matrix, compute_time_weights, temporal_split, LOGISTIC_FEATURES` | WIRED | Lines 38-43 confirmed |
| `src/model/__init__.py` | `src/model/bayesian.py` | `MODEL_REGISTRY["bayesian_v1"]` via lazy wrappers | WIRED | Lines 13-20, 27: `_lazy_bayesian_train` / `_lazy_bayesian_predict` delegates on call |
| `src/model/ensemble.py` | `src/model/__init__.py` | `from src.model import MODEL_REGISTRY` | WIRED | Line 58 inside `train()` function; iterates `COMPONENT_MODELS` against registry |
| `src/model/ensemble.py` | `src/model/predictor.py` | Ensemble `calibrated_prob` feeds `compute_ev` unchanged | WIRED | `predict()` returns `{"calibrated_prob": blended}`; `TestEnsembleEVIntegration` confirms `compute_ev(prob, 2.10)` works |
| `src/backtest/walk_forward.py` | `src/model/__init__.py` | `MODEL_REGISTRY` dispatched in `_train_model_for_fold` | WIRED | Line 26 import; used in `ensemble_v1` branch |
| `src/backtest/walk_forward.py` | `src/model/base.py` | `build_xgb_training_matrix(conn, train_end)` in xgboost_v1 and ensemble_v1 branches | WIRED | Lines 482, 518; `_FOLD_XGB_TEST_MATCHES_SQL` mirrors `_BUILD_XGB_MATRIX_SQL` column order |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| MOD-02 | 07-02-PLAN.md | System trains gradient boosting model (XGBoost) with isotonic calibration for match outcome prediction | SATISFIED | `src/model/xgboost_model.py`: XGBClassifier with Optuna TPE search, dual sigmoid/isotonic calibration auto-selects lower Brier; `MODEL_REGISTRY["xgboost_v1"]` callable |
| MOD-03 | 07-03-PLAN.md | System trains Bayesian model with credible intervals for match outcome prediction using PyMC | SATISFIED | `src/model/bayesian.py`: PyMC hierarchical logistic, NUTS sampler (draws=2000, tune=1000, chains=2), `predict` returns p5/p50/p95 + calibrated_prob; `MODEL_REGISTRY["bayesian_v1"]` callable |
| MOD-04 | 07-01-PLAN.md + 07-04-PLAN.md | System provides multi-model ensemble that blends predictions weighted by recent calibration performance | SATISFIED | `src/model/ensemble.py`: inverse Brier score weighting, graceful degradation; `walk_forward.py` multi-model dispatch with correct feature dimensions per model; `MODEL_REGISTRY["ensemble_v1"]` callable |

No orphaned requirements: all three IDs declared in plan frontmatter map to implemented artifacts.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|---------|--------|
| `src/backtest/walk_forward.py` | 666, 677, 688, 706 | `return [], bankroll` | Info | Legitimate error-guard returns when fold data is insufficient or training fails — not stubs |

No blockers or warnings found. All `return null`/empty patterns are intentional error guards.

### Human Verification Required

None. All must-haves and key links are verifiable programmatically. The ensemble weight computation, Bayesian credible intervals, XGBoost feature importance, and multi-model walk-forward dispatch are all covered by automated tests (137 pass).

One item that benefits from human confirmation when running on real data:

**Bayesian NUTS convergence in production**
- **Test:** Run `python -c "from src.model.bayesian import train; ..."` against a real populated DB
- **Expected:** `max_rhat < 1.1` logged as converged; p5 <= p50 <= p95 for all predictions
- **Why human:** Tests mock MCMC sampling; actual convergence depends on real data volume and chain mixing — only observable at runtime with real data

### Gaps Summary

No gaps. All phase 07 must-haves are verified at all three levels (exists, substantive, wired):

- The registry-based model architecture (Plan 01) is correctly implemented: `base.py` holds shared utilities, `logistic.py` is registry-compliant with backward-compat `train_and_calibrate`, `trainer.py` is a thin re-export shim, and `MODEL_REGISTRY` with `logistic_v1` was the foundation.
- XGBoost (Plan 02, MOD-02) uses the full 28-column `XGB_FEATURES` set (not the 12-column logistic subset), Optuna TPE tuning with `TimeSeriesSplit` (no future leakage), dual calibration, and feature importance extraction.
- Bayesian (Plan 03, MOD-03) implements PyMC hierarchical logistic with surface partial pooling, NUTS sampler with configurable draws/tune/chains, `pm.Data` containers for out-of-sample prediction, r_hat convergence checking, and p5/p50/p95 output.
- Ensemble + Walk-forward (Plan 04, MOD-04) implements inverse Brier score weighting, graceful degradation, EV-compatible `calibrated_prob` output, and correct 28-column vs 12-column feature dimension routing in `walk_forward.py`.
- All 137 tests pass (test_model.py 52 + test_model_registry.py 17 + test_model_xgboost.py 19 + test_model_bayesian.py 21 + test_ensemble.py 12 + test_walk_forward_multimodel.py 10 + additional existing tests).
- predictions schema has p5/p50/p95 nullable REAL columns for Bayesian CI storage.
- Note: XGB_FEATURES has 28 entries (not 27 as plan comments suggested) — this is documented in SUMMARY files as an auto-fixed count correction; the actual feature list matches the plan spec.

---

_Verified: 2026-03-18_
_Verifier: Claude (gsd-verifier)_
