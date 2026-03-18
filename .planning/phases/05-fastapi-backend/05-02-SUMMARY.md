---
phase: 05-fastapi-backend
plan: "02"
subsystem: api
tags: [fastapi, sqlalchemy, async, endpoints, backtest, predictions, calibration]
dependency_graph:
  requires: ["05-01"]
  provides: ["06-01"]
  affects: []
tech_stack:
  added: []
  patterns:
    - async SQLAlchemy text() queries with named parameter binding
    - Dynamic WHERE clause construction via conditions list
    - PRAGMA foreign_keys=OFF in test seeder for leaf-table inserts
    - engine.begin() connection context for FK-scoped test setup
key_files:
  created:
    - src/api/routers/predict.py
    - src/api/routers/backtest.py
    - src/api/routers/bankroll.py
    - src/api/routers/models.py
    - src/api/routers/calibration.py
  modified:
    - src/api/main.py
    - tests/test_api.py
decisions:
  - props.py GET stub already existed from Plan 01 scaffolding — reused without changes
  - PRAGMA foreign_keys=OFF required per-connection (not global) for aiosqlite in-memory seeding
  - engine.begin() used for seeding (not session factory) to have direct connection control
  - BacktestBetRow excludes kelly_full/flat_bet columns (not in schema response model)
metrics:
  duration_seconds: 455
  completed_date: "2026-03-18"
  tasks_completed: 2
  files_created: 5
  files_modified: 2
---

# Phase 5 Plan 02: FastAPI Read Endpoints Summary

**One-liner:** Eight async GET endpoints serving pre-computed backtest/prediction data to the React dashboard with 5-dimension ROI breakdowns, pagination, equity curve construction, and calibration bin parsing.

## What Was Built

Six routers implementing all read-only GET endpoints that serve the React dashboard:

- **predict.py** — `GET /api/v1/predict`: Returns positive-EV prediction rows with dynamic filters (model, min_ev, surface via EXISTS subquery, date_from/date_to)
- **backtest.py** — `GET /api/v1/backtest` + `GET /api/v1/backtest/bets`: Aggregate summary with 5 breakdowns (surface, tourney_level, year, ev_bucket, rank_tier) + paginated bet rows
- **bankroll.py** — `GET /api/v1/bankroll`: Equity curve with initial/current/peak/max_drawdown computed from ordered backtest_results rows
- **models.py** — `GET /api/v1/models`: Per-model metrics joining backtest_results (ROI) and predictions (brier, log_loss) with calibration_quality heuristic
- **calibration.py** — `GET /api/v1/calibration`: Reliability diagram data from calibration_data table, JSON-parsing bin_midpoints/empirical_freq, preferring 'overall' fold
- **props.py** (pre-existing) — `GET /api/v1/props`: Stub returning status="not_available"

All endpoints registered in main.py with direct imports (replaced try/except scaffolding).

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | predict, backtest, bankroll routers | 540d769 |
| 2 | models, calibration, props + main.py + 33 integration tests | bb87bf4 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] props.py already existed from Plan 01**
- **Found during:** Task 2
- **Issue:** Plan called for creating props.py, but it was already created in Plan 01 with the correct GET stub
- **Fix:** Skipped recreation; verified existing implementation matched spec (status="not_available", data=[])
- **Files modified:** None
- **Commit:** N/A

**2. [Rule 1 - Bug] Test seeder FK constraint failure**
- **Found during:** Task 2 verification
- **Issue:** In-memory SQLite with PRAGMA foreign_keys=ON (from schema.sql) blocked inserts into predictions/backtest_results without parent match rows
- **Fix:** Issue `PRAGMA foreign_keys = OFF` at the start of the same `engine.begin()` context as the INSERT statements (SQLite PRAGMA is connection-scoped)
- **Files modified:** tests/test_api.py
- **Commit:** bb87bf4

## Test Coverage

33 tests passing:

- 6 Plan 01 smoke tests (health, openapi, error format)
- 4 predict tests (endpoint shape, field validation, min_ev filter, empty-without-data)
- 4 backtest summary tests (schema keys, n_bets count, breakdown labels)
- 4 backtest/bets tests (pagination, schema keys, offset, year filter)
- 5 bankroll tests (keys, curve list, point fields, initial value, empty-without-data)
- 3 models tests (endpoint, fields, logistic_v1 present)
- 5 calibration tests (endpoint, bin fields, fold filter, overall preference, empty-without-data)
- 2 props stub tests (status value, empty data list)

## Self-Check

Files created/modified:
- `src/api/routers/predict.py` — EXISTS
- `src/api/routers/backtest.py` — EXISTS
- `src/api/routers/bankroll.py` — EXISTS
- `src/api/routers/models.py` — EXISTS
- `src/api/routers/calibration.py` — EXISTS
- `src/api/main.py` — EXISTS (modified)
- `tests/test_api.py` — EXISTS (modified)

Commits:
- 540d769 — Task 1
- bb87bf4 — Task 2

## Self-Check: PASSED
