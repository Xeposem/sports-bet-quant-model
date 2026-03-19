---
phase: 08-player-props
plan: 03
subsystem: ui
tags: [react, nivo, tanstack-query, typescript, vitest]

# Dependency graph
requires:
  - phase: 08-02
    provides: GET /props, POST /props, GET /props/accuracy API endpoints and PropPrediction schema
  - phase: 06-react-dashboard-core
    provides: TabNav component, KpiCard, EmptyState, SkeletonCard shared components, nivoTheme, apiFetch client

provides:
  - Props tab as 5th dashboard tab with inline prop entry form
  - PmfChart component with ThresholdLayer SVG overlay (amber dashed line)
  - useProps, useSubmitPropLine, usePropAccuracy hooks
  - PropPrediction, PropLineEntry, PropLineResponse, PropsListResponse, PropAccuracyBin, PropAccuracyResponse TypeScript interfaces
  - Value badges (Value/Marginal/No Value) color-coded by P(hit) thresholds
  - Accuracy KPI cards and calibration scatter chart via CalibrationChart reuse

affects: [09-simulation-signals-paper-trading]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - ThresholdLayer SVG layer pattern for Nivo charts (same as DiagonalLayer in CalibrationChart)
    - useSubmitPropLine refetches GET /props after POST to find matching prediction by id
    - PropLineResponse type added to handle POST /props response shape separately from PropPrediction

key-files:
  created:
    - dashboard/src/hooks/useProps.ts
    - dashboard/src/components/charts/PmfChart.tsx
    - dashboard/src/tabs/PropsTab.tsx
    - dashboard/src/__tests__/PropsTab.test.tsx
  modified:
    - dashboard/src/api/types.ts
    - dashboard/src/components/layout/TabNav.tsx

key-decisions:
  - "useSubmitPropLine handles POST response as PropLineResponse (id only), then refetches GET /props to find matching PropPrediction by id"
  - "PropLineResponse type added separately from PropPrediction -- POST returns minimal record, GET returns full prediction with pmf/p_hit"
  - "PmfChart slices pmf array to mu +/- 15 range to avoid rendering 50+ empty bars at chart edges"

patterns-established:
  - "ThresholdLayer as any in Nivo layers array -- same escape hatch as DiagonalLayer in CalibrationChart"
  - "Hooks follow useBacktest.ts pattern: useQuery for GET, useMutation for POST with queryClient.invalidateQueries on success"

requirements-completed: [PROP-02, PROP-03]

# Metrics
duration: 45min
completed: 2026-03-19
---

# Phase 8 Plan 03: Player Props Dashboard Tab Summary

**Props dashboard tab with inline PMF prediction form, ThresholdLayer bar chart, value badges, and accuracy KPIs using NegBin model output**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-03-19
- **Completed:** 2026-03-19
- **Tasks:** 3 (2 code + 1 human verification checkpoint)
- **Files modified:** 6

## Accomplishments

- Complete PropsTab component as the 5th dashboard tab: KPI row, inline prop entry form, PMF bar chart with dashed amber threshold line, rolling hit rate and calibration accuracy charts
- PmfChart component with custom ThresholdLayer SVG layer rendering a vertical dashed amber line at the entered line value, green/slate bar coloring by direction
- useProps, useSubmitPropLine, usePropAccuracy hooks with correct POST/GET two-step flow for retrieving full prediction after line entry
- 6 smoke tests passing in PropsTab.test.tsx covering form rendering, KPI cards, empty states, and loading skeletons

## Task Commits

Each task was committed atomically:

1. **Task 1: Types, hooks, PmfChart, and PropsTab component** - `4c1d26f` (feat)
2. **Task 2: TabNav integration and frontend tests** - `ba01118` (feat)
3. **Task 3: Visual verification of Props tab** - checkpoint (no code commit — human approval)

## Files Created/Modified

- `dashboard/src/api/types.ts` - Extended with PropPrediction, PropLineEntry, PropLineResponse, PropsListResponse, PropAccuracyBin, PropAccuracyResponse interfaces
- `dashboard/src/hooks/useProps.ts` - useProps, useSubmitPropLine, usePropAccuracy hooks wired to /props and /props/accuracy endpoints
- `dashboard/src/components/charts/PmfChart.tsx` - PMF bar chart with ThresholdLayer SVG overlay, green/slate bars by direction, amber dashed threshold line
- `dashboard/src/tabs/PropsTab.tsx` - Full Props tab: KPI cards, inline entry form with shadcn Select fields, PMF chart section with value badges, rolling hit rate and calibration scatter sections
- `dashboard/src/components/layout/TabNav.tsx` - Added Props as 5th TabsTrigger and TabsContent
- `dashboard/src/__tests__/PropsTab.test.tsx` - 6 smoke tests: renders heading, KPI cards, empty state, loading skeletons

## Decisions Made

- useSubmitPropLine issues POST which returns PropLineResponse (id + line metadata only), then immediately refetches GET /props and finds the matching PropPrediction by id to populate the PMF chart — the two-step flow is required because the POST does not return the full pmf/p_hit payload
- PropLineResponse added as a separate type from PropPrediction to correctly model the POST response shape
- PmfChart slices the pmf array to `[max(0, floor(mu)-15), min(length, ceil(mu)+15)]` to prevent 50+ empty bars from rendering at chart edges for realistic distribution display

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed useSubmitPropLine to correctly handle POST response**
- **Found during:** Task 1 (hooks implementation)
- **Issue:** Plan specified `onSuccess invalidates ['props'] query` but POST /props returns PropLineResponse (id + line fields), not PropPrediction with pmf. Setting returned object as the active prediction would show undefined pmf/p_hit.
- **Fix:** Added PropLineResponse type; onSuccess handler refetches GET /props and finds the matching PropPrediction by id to load into local state for PMF chart display
- **Files modified:** dashboard/src/api/types.ts, dashboard/src/hooks/useProps.ts
- **Verification:** TypeScript compiles without errors; chart correctly populates after form submission
- **Committed in:** 4c1d26f (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in POST/GET response handling)
**Impact on plan:** Fix was necessary for correct behavior — without it, the PMF chart would never render after prop line submission. No scope creep.

## Issues Encountered

None beyond the auto-fixed POST response type mismatch.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 8 is now complete: PROP_REGISTRY, NegBin/Poisson models, API endpoints, and Props dashboard tab all implemented
- Phase 9 (Simulation, Signals & Paper Trading) can begin: Monte Carlo bankroll simulation, automated EV signal generation, paper trading engine
- Props tab will surface live signals once Phase 9 signal generation is wired in

---
*Phase: 08-player-props*
*Completed: 2026-03-19*
