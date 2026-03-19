---
phase: 08-player-props
plan: 02
subsystem: api
tags: [fastapi, sqlite, props, pmf, pydantic, resolver, pipeline]

# Dependency graph
requires:
  - phase: 08-player-props plan 01
    provides: prop_predictions table, p_over/compute_pmf/predict_and_store in base.py, score_parser, PROP_REGISTRY

provides:
  - GET /props endpoint returning PropPredictionRow objects with p_hit computed from stored PMF
  - GET /props/accuracy endpoint with overall_hit_rate, hit_rate_by_stat, rolling_30d, calibration_bins
  - src/props/resolver.py resolve_props() resolving aces, double_faults, games_won from match data
  - refresh pipeline steps 5 (predict_and_store) and 6 (resolve_props) for automatic prop population

affects: [09-paper-trading, dashboard-props-tab]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - GET /accuracy route registered before empty "" GET route to avoid FastAPI path param conflict
    - p_hit computed server-side as p_over if direction=over else 1-p_over
    - resolve_props joins match_stats through matches table using player_role (winner/loser) not player_id

key-files:
  created:
    - src/props/resolver.py
  modified:
    - src/api/schemas.py
    - src/api/routers/props.py
    - src/refresh/runner.py
    - tests/test_props.py

key-decisions:
  - "GET /accuracy registered before GET '' (empty path) so FastAPI does not treat 'accuracy' as a path parameter"
  - "resolve_props joins match_stats through matches using player_role -- match_stats has no player_id column"
  - "p_hit = p_over if direction='over' else 1-p_over -- consistent with how prop lines are evaluated"
  - "props_predict and props_resolution added as steps 5 and 6 using module-level imports (patchable for tests)"

patterns-established:
  - "Pattern: Accuracy endpoint computes rolling 30-day window by date, uses 10 calibration bins (0.0-1.0)"

requirements-completed: [PROP-02, PROP-03]

# Metrics
duration: 6min
completed: 2026-03-19
---

# Phase 08 Plan 02: Player Props API and Resolution Summary

**GET /props with real PMF-based predictions, GET /props/accuracy with calibration bins, and auto-resolution of aces/double_faults/games_won in the refresh pipeline**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-19T09:15:34Z
- **Completed:** 2026-03-19T09:21:08Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Replaced the GET /props stub (returning status="not_available") with real predictions joined from prop_predictions + prop_lines, with p_hit computed from stored PMF
- Added GET /props/accuracy endpoint returning overall_hit_rate, per-stat rates, rolling 30-day time series, and calibration bins across 10 probability buckets
- Created src/props/resolver.py that resolves aces, double_faults, and games_won predictions against match_stats and parsed scores
- Extended refresh pipeline with step 5 (predict_and_store) and step 6 (resolve_props) so prop_predictions table is populated automatically on every refresh

## Task Commits

Each task was committed atomically:

1. **Task 1: Pydantic schemas, resolver, prediction generation, and refresh pipeline integration** - `952429b` (feat)
2. **Task 2: GET /props and GET /props/accuracy endpoints** - `e433295` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `src/props/resolver.py` - resolve_props(conn) resolves aces/df/games_won from match_stats and match scores
- `src/api/schemas.py` - Added PropPredictionRow, PropsListResponse, PropAccuracyBin, PropAccuracyResponse
- `src/api/routers/props.py` - Rewrote GET /props stub; added GET /props/accuracy endpoint
- `src/refresh/runner.py` - Added step 5 (predict_and_store) and step 6 (resolve_props) to pipeline
- `tests/test_props.py` - Added 7 new tests: 3 resolver unit tests, 4 async endpoint tests

## Decisions Made
- GET /accuracy route registered before GET "" (empty path) so FastAPI routing does not treat the string "accuracy" as a path parameter value
- resolve_props joins match_stats through the matches table using player_role ('winner'/'loser') because match_stats has no direct player_id column
- p_hit computed server-side: p_over(pmf, line_value) if direction='over' else 1 - p_over — consistent evaluation for both directions
- props_predict and props_resolution use module-level imports in runner.py (matching existing pattern) so tests can patch at module scope

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- GET /props now returns live data with p_hit values when prop_lines exist
- GET /props/accuracy tracks prediction accuracy over time with calibration
- Resolver and refresh pipeline fully integrated — prop_predictions auto-populated during refresh
- Ready for Phase 09 paper trading which will consume these endpoints
- Frontend props tab can now display real PMF predictions and accuracy charts

---
*Phase: 08-player-props*
*Completed: 2026-03-19*
