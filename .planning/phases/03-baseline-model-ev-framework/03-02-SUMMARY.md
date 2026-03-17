---
phase: 03-baseline-model-ev-framework
plan: 02
subsystem: model
tags: [scikit-learn, logistic-regression, calibration, brier-score, joblib, sqlite, time-decay]

# Dependency graph
requires:
  - phase: 02-elo-ratings-feature-engineering
    provides: match_features table populated with per-player feature rows per match

provides:
  - src/model/trainer.py: pairwise differential training matrix, time-decay weights, temporal split, calibrated logistic regression pipeline, model serialization
  - src/model/metrics.py: Brier score + log loss + calibration curve data
  - tests/test_model.py: 35 unit tests covering all model behaviors
  - LOGISTIC_FEATURES constant: curated 12-feature list for linear model

affects:
  - 03-03: EV framework consumes calibrated model's predict_proba output
  - 04-backtesting: consumes predictions table and model metrics
  - 06-dashboard: consumes calibration curve data and Brier/log-loss metrics

# Tech tracking
tech-stack:
  added:
    - scikit-learn>=1.4 (LogisticRegression, CalibratedClassifierCV, FrozenEstimator, StandardScaler, brier_score_loss, log_loss, calibration_curve)
    - scipy>=1.10 (implicit dep of sklearn — power method devigging in 03-03)
    - joblib (bundled with sklearn — model serialization)
  patterns:
    - Pairwise differential training: X[i] = winner_features - loser_features, y always 1
    - CalibratedClassifierCV(FrozenEstimator(pipeline)) — sklearn>=1.6 preferred API (cv='prefit' deprecated)
    - Temporal split by index (first 80% train, last 20% val) — no shuffling to prevent look-ahead bias
    - Exponential time-decay weights: exp(-ln(2)*days_ago/half_life_days), floor at 1e-6
    - StandardScaler in Pipeline prevents LogisticRegression ConvergenceWarning from mixed feature scales
    - reference_date parameter on compute_time_weights enables reproducible training vs flexible tests

key-files:
  created:
    - src/model/__init__.py
    - src/model/trainer.py
    - src/model/metrics.py
    - tests/test_model.py
  modified:
    - pyproject.toml (scikit-learn, scipy, rapidfuzz declared as dependencies)

key-decisions:
  - "CalibratedClassifierCV(FrozenEstimator(pipeline)) used instead of cv='prefit' — preferred API in sklearn>=1.6 to avoid deprecation warning (removed in 1.8)"
  - "compute_time_weights reference_date defaults to max date in match_dates for reproducible training; tests pass explicit date for determinism"
  - "h2h_balance is winner.h2h_wins - winner.h2h_losses (not cross-player balance) — captures winner's net H2H record which is the relevant signal"
  - "NULL Elo imputed as 1500.0 via COALESCE in SQL; has_no_elo_w/has_no_elo_l boolean indicators added so model learns to discount uncertain features"
  - "Brier score and log loss are the only metrics (no accuracy) — per MOD-05 requirement"

patterns-established:
  - "Pattern 1: Pairwise differential SQL JOIN — w.player_role='winner' JOIN l.player_role='loser' on same match PK, then JOIN matches for tourney_date"
  - "Pattern 2: FrozenEstimator wraps full sklearn Pipeline before calibration — prevents base classifier retraining during calibration fit"
  - "Pattern 3: Auto-select calibration method — both sigmoid and isotonic are fit on validation set; lower Brier score wins"

requirements-completed: [MOD-01, MOD-05]

# Metrics
duration: 3min
completed: 2026-03-17
---

# Phase 3 Plan 02: Logistic Regression Training Pipeline Summary

**Calibrated logistic regression pipeline with pairwise differential features, exponential time-decay weights, dual Platt/isotonic calibration auto-selection, and Brier/log-loss metrics**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-17T00:28:32Z
- **Completed:** 2026-03-17T00:31:45Z
- **Tasks:** 2 (both TDD — RED + GREEN each)
- **Files modified:** 5

## Accomplishments

- `build_training_matrix` executes a pairwise differential SQL JOIN on match_features, returning X (feature diffs), y (all ones), and chronologically-sorted match dates
- `train_and_calibrate` trains StandardScaler+LogisticRegression pipeline then tries both Platt scaling and isotonic regression on a held-out validation set, auto-selecting whichever achieves the lower Brier score
- `compute_metrics` reports Brier score and log loss (not accuracy) per MOD-05; `calibration_curve_data` provides bin midpoints and empirical frequencies for calibration plots
- 35 unit tests with in-memory SQLite cover all behavioral requirements including imputation logic, temporal ordering, weight decay, and serialization round-trip

## Task Commits

1. **Task 1 (RED): Failing tests for matrix builder, time weights, calibration, metrics** - `7b89bb5` (test)
2. **Task 2 (GREEN): Implementation of trainer.py and metrics.py** - `00355f6` (feat)

**Plan metadata:** (docs commit follows)

_Note: Both tasks used TDD (RED then GREEN). No separate refactor commit needed — deprecation fix applied inline during GREEN._

## Files Created/Modified

- `src/model/__init__.py` — empty package init
- `src/model/trainer.py` — LOGISTIC_FEATURES, build_training_matrix, compute_time_weights, temporal_split, train_and_calibrate, save_model, load_model
- `src/model/metrics.py` — compute_metrics (Brier + log loss), calibration_curve_data
- `tests/test_model.py` — 35 unit tests covering all behaviors (in-memory SQLite, synthetic data)
- `pyproject.toml` — declared scikit-learn>=1.4, scipy>=1.10, rapidfuzz>=3.0 as dependencies

## Decisions Made

- Used `CalibratedClassifierCV(FrozenEstimator(pipeline))` instead of `cv='prefit'` — the former is the sklearn>=1.6 preferred API; `cv='prefit'` is deprecated in 1.6 and removed in 1.8. Eliminates deprecation warning on the installed version (1.6.1).
- `compute_time_weights` defaults `reference_date` to the max date in the input list rather than `date.today()`. This makes training reproducible: running training twice on the same data produces identical weights regardless of when it runs.
- `h2h_balance` is computed as `winner.h2h_wins - winner.h2h_losses` (winner's net H2H record), not a cross-player differential. This captures the winner's historical dominance in this matchup directly.
- NULL Elo values are treated as 1500.0 via `COALESCE` in SQL (the default Glicko-2 starting rating). The `has_no_elo_w` and `has_no_elo_l` boolean indicator columns allow the model to learn to discount predictions where one or both players lack real Elo history.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed CalibratedClassifierCV cv='prefit' deprecation**
- **Found during:** Task 2 (calibration implementation)
- **Issue:** `cv='prefit'` parameter is deprecated in sklearn 1.6 (installed version) and removed in 1.8, producing UserWarning on every calibration fit
- **Fix:** Changed to `CalibratedClassifierCV(FrozenEstimator(pipeline), method=...)` without `cv='prefit'` — the preferred API per sklearn 1.6+ docs
- **Files modified:** src/model/trainer.py
- **Verification:** All 35 tests pass with zero warnings
- **Committed in:** 00355f6 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - deprecation/correctness bug)
**Impact on plan:** Necessary correctness fix — the old API would have broken silently on sklearn 1.8 upgrade. No scope creep.

## Issues Encountered

None — plan executed smoothly. The sklearn version (1.6.1) already had the FrozenEstimator-as-argument API available.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Calibrated model ready for consumption by Phase 03-03 (EV calculation)
- `LOGISTIC_FEATURES` constant is the single source of truth for feature column names — Phase 03-03 must pass matching feature diffs to `model.predict_proba()`
- Model is not yet trained on real data (no real match_features rows yet) — training happens when Phase 2 pipeline has run and populated the DB
- Serialization via `save_model`/`load_model` (joblib) is tested and ready for 03-03 to use

---
*Phase: 03-baseline-model-ev-framework*
*Completed: 2026-03-17*
