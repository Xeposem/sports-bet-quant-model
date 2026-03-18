---
phase: 05-fastapi-backend
plan: "01"
subsystem: api
tags: [fastapi, sqlalchemy, pydantic-v2, async, testing]
dependency_graph:
  requires:
    - src/model/trainer.py (load_model)
    - src/db/connection.py (init_db, _read_schema_sql)
  provides:
    - src/api/main.py (FastAPI app with lifespan)
    - src/api/deps.py (get_db, DbDep)
    - src/api/schemas.py (all Pydantic v2 schemas)
    - src/api/jobs.py (job state management)
    - tests/conftest.py (async_app, async_client fixtures)
  affects:
    - tests/test_api.py (smoke tests)
    - src/db/schema.sql (prop_lines table added)
tech_stack:
  added:
    - fastapi>=0.115.0
    - uvicorn>=0.30.0
    - sqlalchemy>=2.0.0 (async engine + session)
    - aiosqlite>=0.20.0
    - python-multipart>=0.0.9
    - httpx>=0.27.0 (dev)
    - pytest-asyncio>=0.23.0 (dev)
  patterns:
    - asynccontextmanager lifespan for startup/shutdown
    - app.state for shared resources (engine, session_factory, model, db_path)
    - Annotated[AsyncSession, Depends(get_db)] for dependency injection
    - StarletteHTTPException handler for structured JSON errors (catches routing 404s)
    - ConfigDict(from_attributes=True) on all Pydantic v2 models
key_files:
  created:
    - src/api/__init__.py
    - src/api/main.py
    - src/api/deps.py
    - src/api/schemas.py
    - src/api/jobs.py
    - src/api/routers/__init__.py
    - tests/test_api.py
  modified:
    - pyproject.toml
    - src/db/schema.sql
    - tests/conftest.py
decisions:
  - "StarletteHTTPException handler (not FastAPI HTTPException) required to catch routing 404s in FastAPI 0.128+"
  - "greenlet==3.0.3 pinned explicitly — newer versions fail to build on Python 3.9 + Windows"
  - "async_app fixture sets app.state directly, bypassing lifespan, for isolated endpoint tests"
metrics:
  duration: "6 minutes"
  completed: "2026-03-18"
  tasks_completed: 2
  files_created: 7
  files_modified: 3
---

# Phase 5 Plan 1: FastAPI Application Skeleton Summary

**One-liner:** FastAPI app with async SQLAlchemy lifespan, Pydantic v2 schemas, job state management, and httpx async test infrastructure.

## What Was Built

### Task 1: Dependencies, Schema, pytest-asyncio

- Added FastAPI ecosystem deps to `pyproject.toml`: fastapi, uvicorn, sqlalchemy, aiosqlite, python-multipart (main); httpx, pytest-asyncio (dev)
- Configured `asyncio_mode = "auto"` in pytest ini_options
- Added `prop_lines` table to `src/db/schema.sql` for manual PrizePicks line entry (no FK to players since manual entry may lack resolved player_id)

### Task 2: FastAPI App, Schemas, Deps, Jobs, Tests

**src/api/main.py** — FastAPI app with:
- `asynccontextmanager` lifespan: creates async SQLAlchemy engine + session factory, loads model via `run_in_executor` (warns and continues if missing), stores all on `app.state`
- CORS middleware: configurable via `CORS_ORIGINS` env var, defaults to localhost:3000/5173
- Structured JSON error handler (catches `StarletteHTTPException` for routing 404s)
- `GET /api/v1/health` endpoint
- Try/except router registration pattern for future routers

**src/api/deps.py** — `get_db` async generator + `DbDep` annotated type alias

**src/api/schemas.py** — 22 Pydantic v2 models covering: predictions, backtest results, bankroll curve, model metrics, calibration, odds, props, job status

**src/api/jobs.py** — Module-level `job_states` dict with `create_job`, `update_job`, `get_job`

**tests/conftest.py** — `async_app` and `async_client` fixtures (appended to existing sync fixtures)

**tests/test_api.py** — 6 smoke tests: /docs (OpenAPI UI), /api/v1/health (status+model_loaded), 404 structured JSON format

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] StarletteHTTPException required instead of FastAPI HTTPException for routing 404s**
- **Found during:** Task 2 — test_error_response_has_required_keys failed
- **Issue:** FastAPI 0.128.8 routing 404s are raised as `starlette.exceptions.HTTPException`, not `fastapi.HTTPException`. The decorator `@app.exception_handler(HTTPException)` only catches explicitly raised HTTPException, not Starlette routing errors.
- **Fix:** Changed handler to catch `StarletteHTTPException` (imported from `starlette.exceptions`)
- **Files modified:** src/api/main.py
- **Commit:** e45e491

**2. [Rule 3 - Blocking] greenlet build failure on Python 3.9 + Windows**
- **Found during:** Task 1 — `pip install sqlalchemy` failed building greenlet wheel
- **Issue:** SQLAlchemy 2.x requires greenlet; newer greenlet versions fail to compile on Python 3.9/Windows without MSVC headers matching
- **Fix:** Explicitly installed `greenlet==3.0.3` (pre-built wheel available for cp39-win_amd64) before SQLAlchemy
- **Files modified:** none (runtime fix only)
- **Commit:** N/A (pip install)

## Self-Check: PASSED

All created files verified on disk. Both task commits confirmed:
- 61fb089: chore(05-01) — deps + schema
- e45e491: feat(05-01) — app skeleton + tests
