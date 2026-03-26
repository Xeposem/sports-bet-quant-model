---
phase: 15-explore-prop-markets-negbin-models-may-have-more-edge-on-aces-and-games-than-the-moneyline-model
plan: 03
subsystem: props-api
tags: [fastapi, pydantic, sqlite3, pytest, backtest, calibration]

# Dependency graph
requires:
  - phase: 15-plan-01
    provides: "Enhanced prop models, extended features, CSI integration"
  - phase: 15-plan-02
    provides: "6 stat type models, score_parser extensions, expanded PROP_REGISTRY"
provides:
  - "GET /props/backtest endpoint: 2023+ hit rate and calibration analysis"
  - "PropBacktestResponse schema (PropBacktestStatRow, PropBacktestCalibrationBin, PropBacktestRollingRow)"
  - "_VALID_STAT_TYPES expanded to all 6 stat types in POST /props validation"
  - "get_props_accuracy hits_by_stat updated to cover all 6 types"
affects:
  - src/api/routers/props.py
  - src/api/schemas.py
  - tests/test_props.py

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Read-only backtest endpoint computes stats in-process via run_in_executor offload"
    - "No prop_lines JOIN in backtest: uses all resolved prop_predictions directly"
    - "Rolling 30-day hit rate computed per stat type over sorted date list"
    - "Calibration score = mean absolute deviation of 10 probability bins"

# Key files
key-files:
  created: []
  modified:
    - src/api/schemas.py
    - src/api/routers/props.py
    - tests/test_props.py

# Decisions
decisions:
  - "Backtest endpoint uses actual > mu as 'hit' definition (not bookmaker line) — measures model calibration independently of entered lines"
  - "first_set_winner special-cased: mu is P(win) directly, so p_hit_val = mu (no p_over call needed)"
  - "GET /props/backtest registered between /accuracy and '' routes to avoid path param conflict"

# Metrics
metrics:
  duration_minutes: 15
  completed_date: "2026-03-25"
  tasks_completed: 2
  files_modified: 3
---

# Phase 15 Plan 03: Prop Backtest API Endpoint Summary

**One-liner:** Read-only GET /props/backtest endpoint computing 2023+ hit rate, calibration bins, and rolling 30-day accuracy per stat type, with _VALID_STAT_TYPES expanded to all 6 prop types.

## What Was Built

### Task 1: PropBacktestResponse schema and GET /props/backtest endpoint

Added four new Pydantic schemas to `src/api/schemas.py`:
- `PropBacktestStatRow` — per-stat hit rate, n, avg_p_hit, calibration_score
- `PropBacktestCalibrationBin` — stat_type, predicted_p, actual_hit_rate, n
- `PropBacktestRollingRow` — date, stat_type, hit_rate
- `PropBacktestResponse` — top-level response combining all three

Updated `src/api/routers/props.py`:
- `_VALID_STAT_TYPES` expanded from 3 to 6 (added breaks_of_serve, sets_won, first_set_winner)
- `hits_by_stat` default dict in `get_props_accuracy` updated to cover all 6 types in both the empty-response and computed-response paths
- `GET /props/backtest` endpoint registered between `/accuracy` and `""` routes (correct order to avoid path param conflicts)

The backtest endpoint:
- Queries all `prop_predictions` where `actual_value IS NOT NULL AND match_date >= '2023-01-01'`
- No prop_lines JOIN — measures model calibration independently of which lines were entered
- Computes hit rate, avg_p_hit, calibration score per stat type
- Builds 10-bucket calibration bins and 30-day rolling hit rate series
- Returns read-only data (no INSERT/UPDATE SQL)

### Task 2: Integration tests

Added three tests to `tests/test_props.py`:
- `test_get_props_backtest` — seeds 6 resolved predictions (3 aces, 3 games_won), asserts 200 status, correct structure, non-empty by_stat_type with hit_rate bounds
- `test_get_props_backtest_empty` — asserts 200 status with empty lists when no resolved predictions exist
- `test_valid_stat_types_expanded` — directly verifies `_VALID_STAT_TYPES` equals the expected 6-element set

## Verification

- `python -c "from src.api.schemas import PropBacktestResponse"` succeeds
- Routes list includes `/props/backtest`
- `python -m pytest tests/test_props.py -q` exits 0 (41 passed)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — endpoint is fully wired to the `prop_predictions` table.

## Self-Check: PASSED

- `src/api/schemas.py` contains PropBacktestResponse: confirmed
- `src/api/routers/props.py` contains `/backtest` route: confirmed
- `tests/test_props.py` contains `test_get_props_backtest`: confirmed
- Task 1 commit `14090a6`: confirmed
- Task 2 commit `b26974e`: confirmed
