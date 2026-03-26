---
phase: 15-explore-prop-markets-negbin-models-may-have-more-edge-on-aces-and-games-than-the-moneyline-model
plan: 01
subsystem: props
tags: [statsmodels, glm, negbin, poisson, aic, time-decay, court-speed-index, pinnacle]

# Dependency graph
requires:
  - phase: 08-player-props
    provides: aces/double_faults/games_won NegBin GLM models with PROP_REGISTRY
  - phase: 14-court-speed-index
    provides: court_speed_index table with csi_value per tourney_id

provides:
  - All 3 prop models (aces, double_faults, games_won) enhanced with 5+ new covariates
  - Auto Poisson/NegBin selection via AIC in all 3 models
  - Exponential time-decay weighting (365-day half-life) in all 3 train() functions
  - predict_and_store passes court_speed_index, pinnacle_prob, opp_bp_rate to all models
  - H2H ace rate for aces model; h2h_games_rate for games_won

affects:
  - 15-02: new stat types build on same enhanced pattern
  - 15-03: prop backtesting uses enhanced models
  - 15-04: dashboard displays predictions from enhanced models

# Tech tracking
tech-stack:
  added: []
  patterns:
    - compute_time_weights used with var_weights in GLM fit (not freq_weights)
    - CASE WHEN COUNT(*) >= 3 pattern for correlated subqueries in SQLite (HAVING without GROUP BY not allowed)
    - H2H subquery returns NULL when < 3 matches, filled with avg_* fallback in Python

key-files:
  created: []
  modified:
    - src/props/aces.py
    - src/props/double_faults.py
    - src/props/games_won.py
    - src/props/base.py
    - tests/test_props.py

key-decisions:
  - "SQLite HAVING without GROUP BY not valid — used CASE WHEN COUNT(*) >= 3 pattern in correlated H2H subquery"
  - "H2H games_rate uses 0.0 default (not player avg) — games_won is match-length dependent, player avg not a meaningful H2H proxy"
  - "var_weights used in GLM fit (not freq_weights) — matches Phase 3 compute_time_weights decision in RESEARCH.md Pitfall 1"
  - "games_won h2h_games_rate filled to 0.0 via .fillna().astype(float) — avoids pandas FutureWarning from object dtype downcasting"

patterns-established:
  - "Pattern 1: LEFT JOIN court_speed_index on tourney_id+tour in training SQL; COALESCE csi_value to 0.5 default"
  - "Pattern 2: Pinnacle prob via CASE ms.player_role WHEN winner THEN pinnacle_prob_winner ELSE pinnacle_prob_loser"
  - "Pattern 3: AIC auto-select — aces/double_faults: NegBin if negbin_aic < poisson_aic - 2; games_won: Poisson only if poisson_aic < negbin_aic - 2"

requirements-completed: [D-04, D-05, D-06, D-07, D-08]

# Metrics
duration: 6min
completed: 2026-03-25
---

# Phase 15 Plan 01: Prop Model Enhancement Summary

**All 3 prop models enhanced in-place with court speed index, Pinnacle probability, opponent BP rate, H2H stat history, exponential time-decay weighting, and automatic Poisson/NegBin selection via AIC**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-25T00:32:00Z
- **Completed:** 2026-03-25T00:38:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Updated `_FORMULA` strings in all 3 model files with 4-6 new covariates (CSI, Pinnacle, opp_bp_rate, H2H stats)
- Added `compute_time_weights` import and `var_weights=weights` to all 3 `train()` functions (365-day half-life)
- Added `court_speed_index` LEFT JOIN and `match_date` column to all 3 `_build_training_df()` SQL queries
- Updated `predict_and_store` in base.py to include CSI + Pinnacle JOIN and pass 7 new features to models
- Added 2 new tests: `test_time_decay_weights` and `test_predict_and_store_includes_csi_features`; all 29 tests pass

## Task Commits

1. **Task 1: Enhance 3 existing prop model training** - `cb8a861` (feat)
2. **Task 2: Update predict_and_store query with CSI + Pinnacle JOINs** - `d8c3d20` (feat)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified

- `src/props/aces.py` - Updated formula, SQL, train() with time-decay, predict() with new features, H2H subquery
- `src/props/double_faults.py` - Updated formula, SQL, train() with time-decay, predict() with new features
- `src/props/games_won.py` - Updated formula, SQL, train() with time-decay, predict() with new features, h2h_games_rate
- `src/props/base.py` - predict_and_store SQL updated with court_speed_index JOIN; feature_row now includes 7 new fields
- `tests/test_props.py` - Added court_speed_index + pinnacle columns to test DB schema; 2 new tests added

## Decisions Made

- SQLite does not support `HAVING` without `GROUP BY` in correlated subqueries — used `CASE WHEN COUNT(*) >= 3 THEN AVG(...) ELSE NULL END` pattern
- H2H games rate defaults to `0.0` rather than player average — games won is match-length dependent and not a meaningful fallback from player history
- `var_weights` used in GLM `.fit()` (not `freq_weights`) to match Phase 3 `compute_time_weights` design (RESEARCH.md Pitfall 1 note)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed SQLite HAVING without GROUP BY error in H2H correlated subquery**
- **Found during:** Task 1 verification (test run)
- **Issue:** Plan specified `HAVING COUNT(*) >= 3` in correlated subquery; SQLite requires GROUP BY before HAVING — throws `OperationalError: a GROUP BY clause is required before HAVING`
- **Fix:** Replaced `HAVING COUNT(*) >= 3` with `CASE WHEN COUNT(*) >= 3 THEN AVG(...) ELSE NULL END` in SELECT, returning NULL for insufficient H2H history
- **Files modified:** src/props/aces.py
- **Verification:** 27 tests pass after fix
- **Committed in:** cb8a861 (Task 1 commit)

**2. [Rule 2 - Missing Critical] Added court_speed_index and pinnacle columns to test DB schema**
- **Found during:** Task 1 verification (test run)
- **Issue:** `_make_test_db_with_data()` test helper lacked `court_speed_index` table and `pinnacle_prob_winner/loser/has_no_pinnacle` columns in `match_features` — caused `OperationalError: no such table: court_speed_index`
- **Fix:** Added `CREATE TABLE IF NOT EXISTS court_speed_index` and 3 new columns to `match_features` in the test helper
- **Files modified:** tests/test_props.py
- **Verification:** All 27 tests pass after fix
- **Committed in:** cb8a861 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical test infrastructure)
**Impact on plan:** Both auto-fixes were necessary for correctness. No scope creep.

## Issues Encountered

- pandas FutureWarning about object dtype downcasting in games_won.py (`fillna(0.0)` on None-typed column) — fixed with `.astype(float)` but warning persists; non-blocking, all tests pass

## Known Stubs

None — all new features are wired through to the training SQL and predict() function. CSI and Pinnacle columns use `COALESCE` defaults (0.5) when data is absent, so models work on production data immediately.

## Next Phase Readiness

- All 3 enhanced models ready for retraining on real data
- New feature columns (court_speed_index, pinnacle_prob, opp_bp_rate, h2h_ace_rate) passed through predict_and_store
- Ready for Plan 02: new stat types (breaks_of_serve, sets_won, first_set_winner)

---
*Phase: 15-explore-prop-markets-negbin-models-may-have-more-edge-on-aces-and-games-than-the-moneyline-model*
*Completed: 2026-03-25*
