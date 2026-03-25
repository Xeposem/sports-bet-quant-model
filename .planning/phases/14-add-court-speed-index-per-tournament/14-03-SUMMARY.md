---
phase: 14-add-court-speed-index-per-tournament
plan: 03
subsystem: api, ui
tags: [court-speed-index, backtest, signals, react, fastapi, pydantic]

# Dependency graph
requires:
  - phase: 14-01
    provides: court_speed_index table with csi_value and tier data per tournament

provides:
  - BacktestSummary schema with by_speed_tier breakdown (Fast/Medium/Slow ROI stats)
  - SignalRecord schema enriched with court_speed_index and court_speed_tier fields
  - Backtest router speed tier breakdown via numpy tercile bounds + LEFT JOIN court_speed_index
  - Signals router CSI enrichment via LEFT JOIN court_speed_index + Python tier classification
  - BacktestTab 6th RoiBarChart for ROI by Court Speed Tier
  - SignalCard CSI badge with tier label and raw value (Fast=red, Medium=gray, Slow=blue)

affects: [dashboard, api, backtest, signals]

# Tech tracking
tech-stack:
  added: [numpy (already present, now used in API routers)]
  patterns:
    - Python-side tercile computation via numpy.percentile before SQL (SQLite lacks PERCENTILE_CONT)
    - LEFT JOIN court_speed_index on tourney_id + tour for CSI enrichment across routers

key-files:
  created: []
  modified:
    - src/api/schemas.py
    - src/api/routers/backtest.py
    - src/api/routers/signals.py
    - dashboard/src/api/types.ts
    - dashboard/src/tabs/BacktestTab.tsx
    - dashboard/src/components/shared/SignalCard.tsx

key-decisions:
  - "numpy.percentile used in API routers for tercile computation — SQLite lacks PERCENTILE_CONT"
  - "BacktestTab layout changed from 4+1 (2x2 grid + full-width) to 4+2 (2x2 grid + 2-column row) to accommodate 6th chart"

patterns-established:
  - "Pattern: CSI tier labels use p33/p67 tercile thresholds computed from all court_speed_index entries"

requirements-completed: [CSI-08, CSI-09, CSI-10]

# Metrics
duration: 3min
completed: 2026-03-25
---

# Phase 14 Plan 03: CSI API Exposure and Dashboard Summary

**CSI data exposed via API and dashboard: backtest speed tier ROI breakdown with numpy tercile classification, signal card CSI badges with Fast/Medium/Slow color coding.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-25T00:00:01Z
- **Completed:** 2026-03-25T00:03:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Extended BacktestSummary schema and router with by_speed_tier breakdown using numpy tercile bounds + court_speed_index LEFT JOIN
- Enriched SignalRecord schema and signals router with court_speed_index and court_speed_tier fields per signal
- Added 6th RoiBarChart to BacktestTab for ROI by Court Speed Tier, converting layout to 3 rows of 2 charts
- Added colored CSI badge to SignalCard (Fast=red, Medium=gray, Slow=blue) with raw CSI value display

## Task Commits

Each task was committed atomically:

1. **Task 1: Add speed tier breakdown to backtest API and CSI to signals API** - `15bf034` (feat)
2. **Task 2: Add speed tier chart to BacktestTab and CSI badge to SignalCard** - `d32de04` (feat)

## Files Created/Modified

- `src/api/schemas.py` - Added by_speed_tier to BacktestSummary; added court_speed_index/court_speed_tier to SignalRecord
- `src/api/routers/backtest.py` - Added numpy import; added speed tier query with p33/p67 bounds and LEFT JOIN court_speed_index; updated BacktestSummary return
- `src/api/routers/signals.py` - Added numpy import; CSI tercile bounds computed before query; LEFT JOIN court_speed_index in signals query; tier classification in result assembly
- `dashboard/src/api/types.ts` - Added by_speed_tier to BacktestSummary; added court_speed_index/court_speed_tier to SignalRecord
- `dashboard/src/tabs/BacktestTab.tsx` - Added speedTierData derivation; rendered 6th RoiBarChart inside new 2-column grid row alongside Rank Tier
- `dashboard/src/components/shared/SignalCard.tsx` - Added CSI badge with tier-conditional color classes and raw value display

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- src/api/schemas.py by_speed_tier field: verified via Python import
- src/api/schemas.py court_speed_index/court_speed_tier fields: verified via Python import
- src/api/routers/backtest.py LEFT JOIN court_speed_index: present
- src/api/routers/backtest.py np.percentile: present
- src/api/routers/signals.py court_speed_index/court_speed_tier: present
- dashboard/src/api/types.ts by_speed_tier: present
- dashboard/src/tabs/BacktestTab.tsx speedTierData + ROI by Court Speed Tier: present
- dashboard/src/components/shared/SignalCard.tsx court_speed_tier/court_speed_index: present
- TypeScript compilation: 0 errors
