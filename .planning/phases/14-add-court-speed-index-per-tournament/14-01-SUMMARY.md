---
phase: 14-add-court-speed-index-per-tournament
plan: "01"
subsystem: features
tags: [court-speed, csi, features, schema, builder]
dependency_graph:
  requires:
    - src/db/schema.sql
    - src/features/builder.py
    - src/features/form.py
  provides:
    - src/features/court_speed.py (CSI computation and player speed affinity)
    - court_speed_index table (per-tournament CSI storage)
    - match_features CSI columns (court_speed_index, has_no_csi, speed_affinity)
  affects:
    - src/features/builder.py (build_feature_row, _insert_feature_row, build_all_features)
    - tests/test_builder.py (EXPECTED_FEATURE_KEYS updated)
tech_stack:
  added: []
  patterns:
    - Percentile-rank normalization for CSI values using numpy
    - has_no_csi=1 fallback indicator mirrors has_no_elo / has_no_pinnacle pattern
    - Idempotent PRAGMA table_info column check for ALTER TABLE migration
    - INSERT OR REPLACE for idempotent court_speed_index population
key_files:
  created:
    - src/features/court_speed.py
    - tests/test_court_speed.py
  modified:
    - src/db/schema.sql
    - src/features/builder.py
    - tests/test_builder.py
decisions:
  - "COUNT(DISTINCT m.match_num) used for min_matches threshold — avoids double-counting winner/loser stat rows (2 rows per match)"
  - "Early-return in compute_court_speed_index counts all_venues for tournaments_skipped even when no rows qualify"
  - "percentile-rank normalization (fraction of values <= current) chosen over min-max — bounded [0,1], robust to outliers"
metrics:
  duration_seconds: 277
  completed_date: "2026-03-25"
  tasks_completed: 2
  files_changed: 5
---

# Phase 14 Plan 01: Court Speed Index Schema and CSI Computation Module Summary

Court Speed Index (CSI) computed from match_stats ace_rate and first_serve_won_pct, stored per tournament in court_speed_index table, with surface-average fallback (has_no_csi=1) and player speed affinity differential integrated into build_feature_row.

## What Was Built

### Task 1: court_speed_index table schema and CSI computation module

- Added `court_speed_index` table DDL to `src/db/schema.sql` with `(tourney_id, tour)` primary key
- Created `src/features/court_speed.py` with four exports:
  - `compute_court_speed_index`: aggregates ace_rate and first_won_pct per tournament using `COUNT(DISTINCT match_num) >= min_matches` threshold, normalizes raw CSI values to [0,1] via percentile rank, stores via `INSERT OR REPLACE`
  - `_get_csi`: tournament lookup with three-tier fallback (exact match → surface average → global average → 0.5 default)
  - `compute_player_speed_affinity`: computes fast_wr - slow_wr using tercile boundaries from all CSI values
  - `migrate_csi_columns`: idempotent ALTER TABLE adding `court_speed_index REAL`, `has_no_csi INTEGER`, `speed_affinity REAL` to match_features

### Task 2: CSI integration into builder.py

- Added `from src.features.court_speed import _get_csi, compute_player_speed_affinity` to builder module imports
- Extended `build_feature_row` to call `_get_csi` and `compute_player_speed_affinity` after Pinnacle section
- Added `court_speed_index`, `has_no_csi`, `speed_affinity` keys to the feature row dict
- Extended `_insert_feature_row` INSERT with 3 new columns (35 total columns now)
- Added `migrate_csi_columns(conn)` and `compute_court_speed_index(conn)` calls at top of `build_all_features` loop
- Updated `EXPECTED_FEATURE_KEYS` in `tests/test_builder.py` to include the 3 new columns

## Test Results

- `tests/test_court_speed.py`: 14 tests, all passing
- `tests/test_builder.py`: 21 tests, all passing (existing tests unaffected)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed min_matches threshold counting stat rows instead of distinct matches**
- **Found during:** Task 1 first test run
- **Issue:** SQL used `COUNT(ms.rowid)` which counts both winner and loser stat rows per match (2 rows per match), so 5 matches = 10 stat rows = met the threshold incorrectly
- **Fix:** Changed to `COUNT(DISTINCT m.match_num)` to count actual matches; updated n_matches column similarly
- **Files modified:** `src/features/court_speed.py`
- **Commit:** 6758fd8

**2. [Rule 1 - Bug] Fixed tournaments_skipped=0 when no tournaments qualify**
- **Found during:** Task 1 test run
- **Issue:** Early return path when `rows` is empty returned `tournaments_skipped=0` instead of counting all venues
- **Fix:** Added `all_venues` query inside the early-return branch
- **Files modified:** `src/features/court_speed.py`
- **Commit:** 6758fd8

**3. [Rule 1 - Bug] Updated EXPECTED_FEATURE_KEYS in test_builder.py**
- **Found during:** Task 2 test run
- **Issue:** `test_all_expected_keys_present` asserted exact key set without the 3 new CSI columns
- **Fix:** Added `court_speed_index`, `has_no_csi`, `speed_affinity` to the expected keys set
- **Files modified:** `tests/test_builder.py`
- **Commit:** 6243e71

## Known Stubs

None — all CSI data flows from real match_stats aggregation. The 0.5 default in `_get_csi` is a documented neutral fallback, not a stub blocking plan goals.

## Self-Check: PASSED

- `src/features/court_speed.py` — FOUND
- `tests/test_court_speed.py` — FOUND
- `src/db/schema.sql` contains `CREATE TABLE IF NOT EXISTS court_speed_index` — FOUND
- `src/features/builder.py` contains `from src.features.court_speed import _get_csi` — FOUND
- Commit 6758fd8 — FOUND
- Commit 6243e71 — FOUND
