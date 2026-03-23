---
phase: 09-simulation-signals-paper-trading
plan: "02"
subsystem: ui
tags: [react, typescript, lightweight-charts, nivo, tanstack-query, monte-carlo]

requires:
  - phase: 09-01
    provides: FastAPI Monte Carlo endpoints (POST /simulation/run, GET /simulation/result)

provides:
  - FanChart component with 5 percentile lines via Lightweight Charts v5
  - HistogramChart component with ruin coloring via Nivo ResponsiveBar
  - MonteCarloSection component with parameter form, KPI cards, and dual charts
  - useSimulationResult query hook and useRunSimulation mutation hook
  - MonteCarloSection integrated into OverviewTab replacing placeholder

affects:
  - Phase 09 plans that add paper trading or signals tabs (MonteCarloSection pattern)

tech-stack:
  added: []
  patterns:
    - "useRunSimulation mutation + cache invalidation pattern (same as useSubmitPropLine)"
    - "Synthetic UTCTimestamp from step index for Lightweight Charts time axis"
    - "isRuin flag on histogram bins drives red/green coloring"

key-files:
  created:
    - dashboard/src/hooks/useSimulation.ts
    - dashboard/src/components/charts/FanChart.tsx
    - dashboard/src/components/charts/HistogramChart.tsx
    - dashboard/src/components/shared/MonteCarloSection.tsx
    - dashboard/src/__tests__/MonteCarloSection.test.tsx
  modified:
    - dashboard/src/api/types.ts
    - dashboard/src/tabs/OverviewTab.tsx

key-decisions:
  - "Synthetic Unix timestamps: step * 86400 + baseTimestamp (Jan 1 2024) satisfies Lightweight Charts strictly-increasing time requirement for step-based Monte Carlo paths"
  - "useRunSimulation.data takes precedence over useSimulationResult.data so fresh mutation results show immediately without needing cache round-trip"
  - "HistogramChart uses renderTick: () => null to hide 20 dense x-axis labels — legend remains for axis identification"

patterns-established:
  - "FanChart pattern: 5 LineSeries on single createChart instance, matching BankrollChart dark theme config"
  - "Histogram bin coloring: isRuin flag (midpoint <= 0) drives red vs green bar colors"
  - "MonteCarloSection: result = runSimulation.data ?? simulationResult.data to show freshest data"

requirements-completed:
  - BANK-03
  - BANK-04

duration: 15min
completed: 2026-03-22
---

# Phase 9 Plan 02: Monte Carlo Frontend Summary

**Monte Carlo simulation frontend with FanChart (5 percentile lines), HistogramChart (ruin-colored histogram), KPI cards, and parameter form wired to POST /simulation/run — integrated into OverviewTab replacing placeholder**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-22T02:20:00Z
- **Completed:** 2026-03-22T02:35:41Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- TypeScript types (PercentilePath, MonteCarloRequest, MonteCarloResult) added to types.ts with useSimulationResult and useRunSimulation hooks
- FanChart renders p5/p25/p50/p75/p95 percentile lines using Lightweight Charts v5 with synthetic timestamps for step-based data
- HistogramChart bins terminal distribution into 20 buckets, colors ruin bins red (midpoint <= 0) via Nivo ResponsiveBar
- MonteCarloSection combines parameter form (seasons/bankroll/Kelly/EV threshold), 3 KPI cards, and side-by-side charts with empty state
- OverviewTab placeholder card replaced with live MonteCarloSection
- 4 component tests passing (empty state, button presence, KPI values, heading)

## Task Commits

Each task was committed atomically:

1. **Task 1: TypeScript types + useSimulation hooks** - `5dc8354` (feat)
2. **Task 2: FanChart + HistogramChart + MonteCarloSection** - `aaf675c` (feat)
3. **Task 3: Wire MonteCarloSection into OverviewTab + tests** - `a2f785c` (feat)

## Files Created/Modified
- `dashboard/src/api/types.ts` - Added PercentilePath, MonteCarloRequest, MonteCarloResult interfaces
- `dashboard/src/hooks/useSimulation.ts` - useSimulationResult query + useRunSimulation mutation hooks
- `dashboard/src/components/charts/FanChart.tsx` - Lightweight Charts v5 fan chart with 5 percentile lines
- `dashboard/src/components/charts/HistogramChart.tsx` - Nivo ResponsiveBar with 20 bins, ruin coloring
- `dashboard/src/components/shared/MonteCarloSection.tsx` - Full simulation section with form, KPIs, charts
- `dashboard/src/tabs/OverviewTab.tsx` - Replaced placeholder with MonteCarloSection import and JSX
- `dashboard/src/__tests__/MonteCarloSection.test.tsx` - 4 vitest tests for component behavior

## Decisions Made
- Synthetic timestamps: `step * 86400 + 1704067200` satisfies Lightweight Charts' strictly-increasing time requirement without needing real dates from the backend
- `runSimulation.data ?? simulationResult.data` precedence ensures fresh mutation results display immediately
- Histogram x-axis tick labels suppressed (`renderTick: () => null`) to avoid 20 dense overlapping labels; axis legend retained

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness
- Monte Carlo simulation fully functional on the Overview tab
- Ready for Plan 03 (Signals tab) and Plan 04 (Paper Trading tab)
- FanChart and HistogramChart reusable if needed in other contexts

---
*Phase: 09-simulation-signals-paper-trading*
*Completed: 2026-03-22*

## Self-Check: PASSED

All files exist, all commits verified, all 4 tests passing.
