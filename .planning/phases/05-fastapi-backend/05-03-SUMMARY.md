---
phase: 05-fastapi-backend
plan: "03"
subsystem: api
tags: [fastapi, sqlite3, asyncio, run_in_executor, rapidfuzz, background-jobs, testing]

dependency_graph:
  requires:
    - src/api/jobs.py (create_job, update_job, get_job)
    - src/api/schemas.py (OddsEntry, PropLineEntry, BacktestRunRequest, JobResponse, etc.)
    - src/odds/linker.py (link_odds_to_matches, fuzzy_link_player)
    - src/odds/ingester.py (import_csv_odds, upsert_match_odds)
    - src/refresh/runner.py (refresh_all)
    - src/backtest/walk_forward.py (run_walk_forward)
    - src/db/connection.py (get_connection, init_db)
  provides:
    - src/api/routers/odds.py (POST /api/v1/odds, POST /api/v1/odds/upload)
    - src/api/routers/props.py (GET /api/v1/props stub, POST /api/v1/props)
    - src/api/routers/refresh.py (POST /api/v1/refresh, GET /api/v1/refresh/status)
    - src/api/routers/backtest.py (POST /api/v1/backtest/run, GET /api/v1/backtest/run/status — appended to existing read router)
    - tests/test_api_write.py (14 integration tests for all write/action endpoints)
  affects:
    - Phase 6 React dashboard — these endpoints provide data input and pipeline control UI
    - Phase 8 props model — prop_lines table now has data via POST /props

tech-stack:
  added: []
  patterns:
    - "sync sqlite3 writes offloaded via asyncio.get_event_loop().run_in_executor(None, sync_fn)"
    - "module-level imports of pipeline functions (refresh_all, run_walk_forward, link_odds_to_matches) enable unittest.mock.patch at module scope in tests"
    - "background job pattern: create_job returns UUID, sync wrapper updates status via update_job, result stored in job_states dict"
    - "async_app test fixture uses tmp_path file DB (not :memory:) so sync sqlite3 writes and async SQLAlchemy engine share same database"
    - "CSV upload: read UploadFile bytes in async, write to tempfile, pass filepath to sync import function, cleanup in finally"

key-files:
  created:
    - src/api/routers/odds.py
    - src/api/routers/props.py
    - src/api/routers/refresh.py
    - tests/test_api_write.py
  modified:
    - src/api/routers/backtest.py (added POST /run and GET /run/status endpoints)
    - tests/conftest.py (updated async_app fixture to use tmp_path file DB)

key-decisions:
  - "Module-level imports (link_odds_to_matches, refresh_all, run_walk_forward) required for unittest.mock.patch at module scope — lazy imports inside closures cannot be patched at the module attribute"
  - "async_app fixture switched from :memory: to tmp_path file DB — sqlite3.connect(':memory:') opens a new empty DB on each call, so sync write endpoints could not share schema with the async test engine"
  - "prop_lines INSERT uses tour='ATP' hardcoded default — no tour in PropLineEntry schema; can be parameterized in Phase 8"

requirements-completed:
  - DASH-08

duration: 25min
completed: "2026-03-17"
---

# Phase 5 Plan 3: Write and Background-Job Endpoints Summary

**7 write/action endpoints with fuzzy player matching, CSV upload, and pollable background jobs for refresh and backtest pipelines**

## Performance

- **Duration:** 25 min
- **Started:** 2026-03-17
- **Completed:** 2026-03-17
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- POST /api/v1/odds accepts JSON body, uses link_odds_to_matches for fuzzy player matching, stores if linked or returns candidates if not
- POST /api/v1/odds/upload accepts CSV via multipart/form-data, writes to temp file, calls import_csv_odds pipeline
- POST /api/v1/props stores manual prop lines with stat_type/direction validation (422 on invalid)
- POST /api/v1/refresh and POST /api/v1/backtest/run trigger long-running pipelines in thread pool, return pollable job IDs
- 14 integration tests covering all write/action endpoints with mocked pipeline functions

## Task Commits

1. **Task 1: Odds entry, CSV upload, prop line endpoints** - `ba9088d` (feat)
2. **Task 2: Refresh and backtest-run background job endpoints; tests** - `1bacf58` (feat)

## Files Created/Modified

- `src/api/routers/odds.py` - POST /odds (fuzzy link + store) and POST /odds/upload (CSV multipart)
- `src/api/routers/props.py` - GET /props stub and POST /props with validation
- `src/api/routers/refresh.py` - POST /refresh and GET /refresh/status background job polling
- `src/api/routers/backtest.py` - Added POST /backtest/run and GET /backtest/run/status to existing read router
- `tests/test_api_write.py` - 14 integration tests for all write/action endpoints
- `tests/conftest.py` - Updated async_app to use tmp_path file DB for sync/async DB sharing

## Decisions Made

- Module-level imports for patchability in tests: `link_odds_to_matches`, `refresh_all`, `run_walk_forward` imported at module level in router files, not inside closures, so `unittest.mock.patch` can intercept them.
- Switched `async_app` fixture from `:memory:` to `tmp_path` file DB: each `sqlite3.connect(":memory:")` call opens a distinct empty database, so sync write endpoints couldn't see the schema. A shared file path ensures both async SQLAlchemy and sync sqlite3 calls use the same database.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Module-level imports required for test patchability**
- **Found during:** Task 1 (test execution)
- **Issue:** Tests used `patch("src.api.routers.odds.link_odds_to_matches")` but the function was imported lazily inside the sync closure — patch target doesn't exist at module attribute level
- **Fix:** Moved all pipeline imports to module level in odds.py, refresh.py, and backtest.py
- **Files modified:** src/api/routers/odds.py, src/api/routers/refresh.py, src/api/routers/backtest.py
- **Verification:** 14 tests pass
- **Committed in:** ba9088d (Task 1), 1bacf58 (Task 2)

**2. [Rule 1 - Bug] async_app fixture :memory: doesn't work for sync write endpoints**
- **Found during:** Task 1 (first test run)
- **Issue:** `sqlite3.connect(":memory:")` creates a fresh empty DB on every call. Write endpoints calling `get_connection(db_path)` with `:memory:` got a table-less DB, causing "no such table: prop_lines" errors
- **Fix:** Updated `async_app` fixture to use `tmp_path / "test.db"` so sync and async connections share the same initialized database
- **Files modified:** tests/conftest.py
- **Verification:** All 14 write tests pass
- **Committed in:** ba9088d (Task 1)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for tests to work. No scope creep.

## Issues Encountered

None beyond the two auto-fixed deviations above.

## Next Phase Readiness

- All 7 write/action endpoints functional and tested (47 total tests pass)
- Background job tracking via in-memory job_states dict supports polling from React dashboard
- Phase 6 (React dashboard) can now consume all API endpoints: read (05-02) and write/action (05-03)
- prop_lines table has write access for Phase 8 props model work

---
*Phase: 05-fastapi-backend*
*Completed: 2026-03-17*
