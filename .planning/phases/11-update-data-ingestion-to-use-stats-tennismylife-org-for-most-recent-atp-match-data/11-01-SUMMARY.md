---
phase: 11-update-data-ingestion-to-use-stats-tennismylife-org-for-most-recent-atp-match-data
plan: 01
subsystem: ingestion
tags: [requests, pandas, sqlite3, tml, tennis-data, player-id-mapping]

# Dependency graph
requires:
  - phase: 01-data-ingestion-storage
    provides: downloader.py pattern, cleaner.py MATCH_DTYPES, loader.py upsert functions, SQLite schema with INTEGER player_id

provides:
  - TML downloader module with download_tml_match_file and download_tml_player_file
  - TML ID mapper with build_id_map, resolve_player_id, normalise_tml_dataframe
  - tml_id_map SQLite table schema for persistent alphanumeric-to-integer ID translation
  - Synthetic integer player IDs starting at 900000 (collision-safe above Sackmann max ~230000)

affects:
  - 11-02-pipeline-integration (will wire these adapters into ingest_year_tml)
  - phase-02 features (player_elo JOINs will work with synthetic integer IDs)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TML downloader mirrors Sackmann downloader interface (same function signatures, return type)
    - Synthetic integer ID translation via INSERT OR IGNORE tml_id_map table (idempotent)
    - build_id_map returns inserted count for idempotency verification
    - normalise_tml_dataframe operates on df.copy() to preserve input immutability

key-files:
  created:
    - src/ingestion/tml_downloader.py
    - src/ingestion/tml_id_mapper.py
    - tests/test_tml_downloader.py
    - tests/test_tml_id_mapper.py
  modified: []

key-decisions:
  - "Synthetic TML player IDs start at 900000 — above Sackmann max (~230000) to guarantee no collision"
  - "build_id_map returns int count of newly inserted rows — callers can verify idempotency"
  - "test assertion for integer type uses numbers.Integral (not int) — accommodates np.int64 from SQLite fetchone"
  - "tml_downloader output filename prefixed tml_YYYY.csv — avoids collision with Sackmann atp_matches_YYYY.csv in same raw_dir"

patterns-established:
  - "Pattern 1: TML downloader — TML_BASE_URL constant + download functions mirroring Sackmann downloader.py"
  - "Pattern 2: ID translation table — tml_id_map with INSERT OR IGNORE for idempotent population"
  - "Pattern 3: normalise_tml_dataframe — df.copy() + apply(resolve_player_id) before entering cleaner pipeline"

requirements-completed: [TML-01, TML-02]

# Metrics
duration: 25min
completed: 2026-03-23
---

# Phase 11 Plan 01: TML Download Adapter and Player ID Translation Layer Summary

**TML downloader and alphanumeric-to-integer ID mapper enabling 2025 ATP match data ingestion via Tennismylife GitHub CSV, with tml_id_map SQLite table assigning synthetic IDs from 900000**

## Performance

- **Duration:** 25 min
- **Started:** 2026-03-23T09:10:00Z
- **Completed:** 2026-03-23T09:35:49Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `src/ingestion/tml_downloader.py` mirroring the Sackmann downloader interface — `download_tml_match_file` fetches `YYYY.csv` from Tennismylife GitHub and writes it as `tml_YYYY.csv`, `download_tml_player_file` fetches `ATP_Database.csv`
- Created `src/ingestion/tml_id_mapper.py` with three functions: `build_id_map` populates a persistent `tml_id_map` table translating TML alphanumeric IDs to synthetic integers starting at 900000; `resolve_player_id` resolves any TML ID to its integer with `KeyError` on unknown; `normalise_tml_dataframe` replaces string winner_id/loser_id columns with integers before the row enters the existing cleaner pipeline
- 19 tests across both files (6 downloader + 13 mapper) all passing; both modules are zero-dependency additions (no new pip packages needed)

## Task Commits

Each task was committed atomically:

1. **Task 1: TML downloader module + tests** - `f933f6e` (feat)
2. **Task 2: TML ID mapper + DataFrame normaliser + tests** - `e9767c9` (feat)

_Note: TDD tasks had test-first (RED) then implementation (GREEN) phases within each commit._

## Files Created/Modified

- `src/ingestion/tml_downloader.py` — TML GitHub CSV downloader; TML_BASE_URL, download_tml_match_file, download_tml_player_file
- `src/ingestion/tml_id_mapper.py` — TML player ID translation; build_id_map, resolve_player_id, normalise_tml_dataframe, _get_next_synthetic_id
- `tests/test_tml_downloader.py` — 6 tests covering URL construction, file writing, 404 error, timeout, absolute path, player file
- `tests/test_tml_id_mapper.py` — 13 tests covering table creation, ID assignment from 900000, idempotency, resolve, KeyError, normalisation, column preservation, input immutability

## Decisions Made

- **Synthetic IDs start at 900000:** Sackmann max player_id is ~230000; 900000 provides a safe gap with no collision risk. This is persisted in `tml_id_map` and never changes for existing players.
- **build_id_map returns inserted count:** Makes callers able to detect first-run vs. subsequent idempotent calls without re-querying.
- **Test integer assertion uses `numbers.Integral`:** `sqlite3.fetchone()` returns `int`, but when the value passes through pandas `apply()`, the lambda returns `np.int64`. Using `numbers.Integral` accommodates both without changing production code.
- **Output filename prefixed `tml_YYYY.csv`:** Prevents collision with Sackmann `atp_matches_YYYY.csv` files in the same `raw_dir` directory.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test assertion for np.int64 vs int**
- **Found during:** Task 2 (normalise_tml_dataframe test)
- **Issue:** Test asserted `isinstance(result, int)` but pandas apply() returned `np.int64` from SQLite row; assertion failed even though the value is functionally an integer
- **Fix:** Changed assertion to use `import numbers; isinstance(result, numbers.Integral)` which accepts both `int` and `np.int64`
- **Files modified:** tests/test_tml_id_mapper.py
- **Verification:** All 13 tests pass
- **Committed in:** e9767c9 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug in test type assertion)
**Impact on plan:** Minor test fix, no production code changes. The implementation follows the plan exactly.

## Issues Encountered

None beyond the np.int64 type assertion issue, which was fixed inline.

## User Setup Required

None - no external service configuration required. All new modules use existing requests, pandas, and sqlite3 libraries already in requirements.txt.

## Next Phase Readiness

- Plan 02 can now import `tml_downloader` and `tml_id_mapper` to wire them into `ingest_year_tml()` in `loader.py`
- The `tml_id_map` table will be created on first call to `build_id_map`; schema is self-initialising
- No blocker: both modules are fully tested and ready for integration

---
*Phase: 11-update-data-ingestion-to-use-stats-tennismylife-org-for-most-recent-atp-match-data*
*Completed: 2026-03-23*
