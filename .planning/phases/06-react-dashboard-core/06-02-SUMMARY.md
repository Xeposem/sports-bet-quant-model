---
phase: 06-react-dashboard-core
plan: "02"
subsystem: frontend
tags: [react, typescript, tanstack-query, lightweight-charts, nivo, vitest]
dependency_graph:
  requires:
    - phase: 06-react-dashboard-core plan 01
      provides: "Vite+React scaffold, API client, TypeScript types, shadcn/ui components, nivoTheme"
  provides:
    - dashboard/src/hooks/useBankroll.ts (TanStack Query hook for /bankroll)
    - dashboard/src/hooks/useBacktest.ts (TanStack Query hooks for /backtest and /backtest/bets)
    - dashboard/src/hooks/useCalibration.ts (TanStack Query hook for /calibration)
    - dashboard/src/hooks/useModels.ts (TanStack Query hook for /models)
    - dashboard/src/hooks/useSignals.ts (TanStack Query hook for /predict)
    - dashboard/src/components/shared/KpiCard.tsx (reusable metric display with trend colors)
    - dashboard/src/components/shared/EmptyState.tsx (centered empty state with optional action)
    - dashboard/src/components/shared/SkeletonCard.tsx (loading skeletons for kpi/chart/table/signal)
    - dashboard/src/components/charts/BankrollChart.tsx (Lightweight Charts BaselineSeries equity curve)
    - dashboard/src/components/charts/CalibrationChart.tsx (Nivo scatter + DiagonalLayer reliability diagram)
    - dashboard/src/tabs/OverviewTab.tsx (fully functional Overview tab with live data)
  affects:
    - 06-03 (Backtest tab — reuses hooks and shared components)
    - 06-04 (Models + Signals tabs — reuses hooks and shared components)
tech-stack:
  added: []
  patterns:
    - "TanStack Query hooks with staleTime: Infinity and retry: 1 for manual-refresh-only data fetching"
    - "Lightweight Charts v5 addSeries(BaselineSeries) API for equity curves"
    - "Nivo custom layer function (DiagonalLayer) injected into layers array for reference lines"
    - "useRef+useEffect lifecycle pattern for Lightweight Charts (create on mount, remove on cleanup)"
    - "Hook mocks use as unknown as ReturnType<...> for TanStack Query v5 type compatibility"
key-files:
  created:
    - dashboard/src/hooks/useBankroll.ts
    - dashboard/src/hooks/useBacktest.ts
    - dashboard/src/hooks/useCalibration.ts
    - dashboard/src/hooks/useModels.ts
    - dashboard/src/hooks/useSignals.ts
    - dashboard/src/components/shared/KpiCard.tsx
    - dashboard/src/components/shared/EmptyState.tsx
    - dashboard/src/components/shared/SkeletonCard.tsx
    - dashboard/src/components/charts/BankrollChart.tsx
    - dashboard/src/components/charts/CalibrationChart.tsx
    - dashboard/src/__tests__/BankrollChart.test.tsx
    - dashboard/src/__tests__/CalibrationChart.test.tsx
    - dashboard/src/__tests__/OverviewTab.test.tsx
  modified:
    - dashboard/src/tabs/OverviewTab.tsx (replaced stub with full implementation)
    - dashboard/src/__tests__/App.test.tsx (updated heading assertion for new OverviewTab)
    - dashboard/src/__tests__/BacktestTab.test.tsx (fixed pre-existing type casts and selector ambiguity)
key-decisions:
  - "useCalibration() called without model arg returns default calibration; called with model_version returns model-specific calibration"
  - "Lightweight Charts v5 addSeries(BaselineSeries, ...) API used, not deprecated addBaselineSeries()"
  - "Hook test mocks use 'as unknown as ReturnType<typeof hook>' — TanStack Query v5 return type is too strict for partial mock objects with just as ReturnType"
  - "App.test.tsx updated to check for Monte Carlo Simulation heading (always rendered) instead of Overview h2 (removed in full OverviewTab)"
  - "Pre-existing BacktestTab.test.tsx getByText selectors changed to getAllByText — filter bar labels and table column headers share identical text"
requirements-completed:
  - DASH-01
  - DASH-03
  - DASH-04
duration: 8min
completed: "2026-03-18"
---

# Phase 06 Plan 02: Overview Tab Summary

**TanStack Query data hooks, KpiCard/EmptyState/SkeletonCard shared components, and a fully functional Overview tab with Lightweight Charts BaselineSeries equity curve, Nivo calibration reliability diagram, and Monte Carlo DASH-04 placeholder**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-18T07:56:11Z
- **Completed:** 2026-03-18T08:04:11Z
- **Tasks:** 2
- **Files modified:** 16

## Accomplishments

- 5 TanStack Query hooks created for all dashboard API endpoints (bankroll, backtest summary, backtest bets, calibration, models, signals) with staleTime: Infinity and retry: 1
- Shared component library extended: KpiCard with positive/negative/neutral trend coloring and aria-label, EmptyState with optional action button and role="status", SkeletonCard with 4 variants and aria-busy="true"
- Overview tab fully built: 4 KPI cards (ROI, P&L, Brier Score, Active Signals), bankroll equity curve using Lightweight Charts BaselineSeries for green-above/red-below start coloring, calibration reliability diagram using Nivo with custom DiagonalLayer SVG reference line, Monte Carlo DASH-04 placeholder card, skeleton loading states, and error alert
- 30 tests pass (8 test files), build exits 0 with zero TypeScript errors

## Task Commits

Each task was committed atomically:

1. **Task 1: TanStack Query hooks and shared components** - `e459d5c` (feat)
2. **Task 2: Overview tab with BankrollChart, CalibrationChart, tests** - `10e93e0` (feat)

## Files Created/Modified

- `dashboard/src/hooks/useBankroll.ts` - queryKey ['bankroll'], staleTime Infinity
- `dashboard/src/hooks/useBacktest.ts` - useBacktestSummary + useBacktestBets with URL params
- `dashboard/src/hooks/useCalibration.ts` - queryKey ['calibration', model]
- `dashboard/src/hooks/useModels.ts` - queryKey ['models']
- `dashboard/src/hooks/useSignals.ts` - queryKey ['signals', params]
- `dashboard/src/components/shared/KpiCard.tsx` - label/value/trend props, aria-label, text-[28px]
- `dashboard/src/components/shared/EmptyState.tsx` - heading/body/action props, role="status"
- `dashboard/src/components/shared/SkeletonCard.tsx` - 4 variants, aria-busy="true"
- `dashboard/src/components/charts/BankrollChart.tsx` - createChart + addSeries(BaselineSeries), green/red coloring
- `dashboard/src/components/charts/CalibrationChart.tsx` - ResponsiveScatterPlot + DiagonalLayer
- `dashboard/src/tabs/OverviewTab.tsx` - full Overview tab replacing stub
- `dashboard/src/__tests__/BankrollChart.test.tsx` - mock lightweight-charts, 3 tests
- `dashboard/src/__tests__/CalibrationChart.test.tsx` - mock @nivo/scatterplot, 2 tests
- `dashboard/src/__tests__/OverviewTab.test.tsx` - mock all hooks, 4 tests
- `dashboard/src/__tests__/App.test.tsx` - updated heading assertion
- `dashboard/src/__tests__/BacktestTab.test.tsx` - fixed pre-existing type casts and selector ambiguity

## Decisions Made

- Lightweight Charts v5 uses `addSeries(BaselineSeries, options)` not the deprecated `addBaselineSeries()` — consistent with v5 API
- Hook test mocks need `as unknown as ReturnType<typeof hook>` because TanStack Query v5 UseQueryResult has 20+ fields; partial mocks cannot satisfy the union type directly
- App.test.tsx heading assertion changed from `getByRole('heading', { name: 'Overview' })` to `{ name: 'Monte Carlo Simulation' }` — the stub h2 "Overview" heading was removed in the full implementation
- BacktestTab.test.tsx `getByText('Surface')` changed to `getAllByText('Surface')` — both the FilterBar label and BetHistoryTable column header render this text

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing test ambiguous getByText selectors in BacktestTab.test.tsx**
- **Found during:** Task 2 (final test run)
- **Issue:** BacktestTab test used `getByText('Surface')`, `getByText('Model')` which failed with "Found multiple elements" because filter bar labels and table column headers share identical text
- **Fix:** Changed to `getAllByText().length >= 1` assertions to handle expected duplicates
- **Files modified:** dashboard/src/__tests__/BacktestTab.test.tsx
- **Verification:** `npx vitest run` exits 0, all 30 tests pass
- **Committed in:** 10e93e0

**2. [Rule 1 - Bug] Fixed pre-existing TypeScript type cast errors in test files**
- **Found during:** Task 2 (npm run build)
- **Issue:** BacktestTab.test.tsx used `as ReturnType<typeof useBacktestBets>` which fails because TanStack Query v5 UseQueryResult is a strict union type — partial mocks can't be narrowed directly
- **Fix:** Changed to `as unknown as ReturnType<...>` for all hook mock return values
- **Files modified:** dashboard/src/__tests__/BacktestTab.test.tsx
- **Verification:** `npm run build` exits 0, zero TypeScript errors
- **Committed in:** 10e93e0

**3. [Rule 1 - Bug] Updated App.test.tsx heading assertion for new OverviewTab content**
- **Found during:** Task 2 (writing OverviewTab)
- **Issue:** App.test.tsx expected `getByRole('heading', { name: 'Overview' })` from the stub, but the full OverviewTab no longer renders an h2 "Overview" heading
- **Fix:** Updated assertion to `{ name: 'Monte Carlo Simulation' }` — a CardTitle always rendered in the Overview tab regardless of loading state
- **Files modified:** dashboard/src/__tests__/App.test.tsx
- **Committed in:** 10e93e0

---

**Total deviations:** 3 auto-fixed (all Rule 1 bug fixes in pre-existing test files)
**Impact on plan:** All fixes resolved pre-existing latent test failures that surfaced once the hooks and full OverviewTab were implemented. No scope creep.

## Issues Encountered

None — all issues were pre-existing test defects resolved via Rule 1 auto-fix.

## Next Phase Readiness

- All TanStack Query hooks ready for use by BacktestTab (Plan 03) and Models/Signals tabs (Plan 04)
- KpiCard/EmptyState/SkeletonCard shared components available for all remaining tabs
- BankrollChart and CalibrationChart components reusable in Models tab (Plan 04)
- Overview tab fully functional with live data fetching, skeleton loading, and error states

---
*Phase: 06-react-dashboard-core*
*Completed: 2026-03-18*
