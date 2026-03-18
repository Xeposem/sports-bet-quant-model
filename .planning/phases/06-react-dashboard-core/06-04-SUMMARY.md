---
phase: 06-react-dashboard-core
plan: "04"
subsystem: frontend
tags: [react, typescript, tanstack-query, nivo, shadcn-ui, vitest, dashboard]
dependency_graph:
  requires:
    - dashboard/src/hooks/useModels.ts
    - dashboard/src/hooks/useCalibration.ts
    - dashboard/src/hooks/useSignals.ts
    - dashboard/src/components/shared/EmptyState.tsx
    - dashboard/src/components/shared/SkeletonCard.tsx
    - dashboard/src/components/shared/FilterBar.tsx
    - dashboard/src/components/charts/nivoTheme.ts
  provides:
    - dashboard/src/components/shared/ModelComparisonTable.tsx
    - dashboard/src/components/shared/SignalCard.tsx
    - dashboard/src/components/charts/CalibrationChart.tsx
    - dashboard/src/tabs/ModelsTab.tsx
    - dashboard/src/tabs/SignalsTab.tsx
  affects:
    - dashboard/src/App.tsx (imports ModelsTab/SignalsTab via tab routing)
tech_stack:
  added: []
  patterns:
    - useState for selectedModel in ModelsTab drives useCalibration(selectedModel) hook
    - Conditional rendering with fade-in transition for CalibrationChart when model selected
    - sortedSignals() pure function derives sorted list from useSignals data + sortBy state
    - Signal card EV color coding as pure CSS border utility classes
key_files:
  created:
    - dashboard/src/components/shared/ModelComparisonTable.tsx
    - dashboard/src/components/shared/SignalCard.tsx
    - dashboard/src/components/charts/CalibrationChart.tsx
    - dashboard/src/__tests__/ModelsTab.test.tsx
  modified:
    - dashboard/src/tabs/ModelsTab.tsx (replaced stub with full implementation)
    - dashboard/src/tabs/SignalsTab.tsx (already implemented in 06-03 commit)
    - dashboard/src/__tests__/SignalsTab.test.tsx (already implemented in 06-03 commit)
    - dashboard/src/components/charts/BankrollChart.tsx (fixed empty state body text)
    - dashboard/src/__tests__/BacktestTab.test.tsx (fixed TypeScript type cast)
decisions:
  - "CalibrationChart empty state heading/body use distinct text to avoid multiple-element test failures with getByText"
  - "BankrollChart empty state body changed from duplicate-prefix pattern to avoid same issue"
  - "Test mocks use 'as unknown as ReturnType<typeof hookFn>' for TanStack Query UseQueryResult type compatibility"
  - "SignalCard omits surface badge — surface field not in PredictionRow, defer to future API enhancement"
metrics:
  duration_minutes: 8
  tasks_completed: 2
  files_created: 4
  files_modified: 5
  completed_date: "2026-03-18"
---

# Phase 06 Plan 04: Models and Signals Tabs Summary

Models tab with clickable model comparison table that loads per-model calibration reliability diagram on row click, and Signals tab with EV-color-coded signal card grid with surface/min-EV filter bar and EV/date sort controls — all 30 tests pass.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | Build ModelComparisonTable, SignalCard, CalibrationChart, ModelsTab with click-to-load calibration | 8789593 | Done |
| 2 | Build SignalsTab with card grid, filter bar, sort controls, empty state, and tests | b0d66a2 | Done (in 06-03 commit) |

## Verification Results

- `npm run build` exits 0 — zero TypeScript errors
- `npx vitest run` — 30 tests passing across 8 test files
- ModelComparisonTable: clickable rows with aria-selected, border-green-500 on selected row
- SignalCard: EV color coded borders (green/amber/slate), role=article
- ModelsTab: click row -> setSelectedModel -> useCalibration(selectedModel) -> CalibrationChart renders
- SignalsTab: responsive grid, EV sort, date sort, filter bar, empty state, skeleton loaders

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Duplicate text in EmptyState heading/body caused getByText ambiguity in tests**
- **Found during:** Task 1 (test run)
- **Issue:** BankrollChart used heading "Bankroll curve unavailable" and body "Bankroll curve unavailable — no backtest data found." Both matched `/Bankroll curve unavailable/i` causing "Found multiple elements" error. CalibrationChart had same pattern.
- **Fix:** Changed body text to be distinct from heading: "No backtest data found. Run a backtest to see the equity curve." / "No calibration data found for this model."
- **Files modified:** dashboard/src/components/charts/BankrollChart.tsx, dashboard/src/components/charts/CalibrationChart.tsx
- **Commit:** 8789593

**2. [Rule 1 - Bug] ModelsTab test `renders column headers` matched /calibration/i in two places**
- **Found during:** Task 1 (test run)
- **Issue:** The column header "Calibration" and the "Click a model row above to view its calibration diagram" prompt both matched `/calibration/i`. getByText threw "Found multiple elements."
- **Fix:** Changed test assertion to use `getAllByText(/^calibration$/i)` for the exact column header match
- **Files modified:** dashboard/src/__tests__/ModelsTab.test.tsx
- **Commit:** 8789593

**3. [Rule 1 - Bug] TypeScript type cast `as ReturnType<typeof useX>` incompatible with TanStack Query UseQueryResult union**
- **Found during:** Task 1 + Task 2 (npm run build)
- **Issue:** TanStack Query `UseQueryResult<T>` is a discriminated union. Direct `as ReturnType<...>` fails TypeScript — the mock object doesn't cover all required properties of `QueryObserverPlaceholderResult`.
- **Fix:** Changed all test mocks to use `as unknown as ReturnType<typeof hookFn>` in BacktestTab.test.tsx, ModelsTab.test.tsx, SignalsTab.test.tsx
- **Files modified:** dashboard/src/__tests__/BacktestTab.test.tsx, dashboard/src/__tests__/ModelsTab.test.tsx, dashboard/src/__tests__/SignalsTab.test.tsx
- **Commit:** 8789593

**4. [Rule 3 - Blocking] CalibrationChart not yet created (Plan 02 missing artifact)**
- **Found during:** Task 1 (checking dependencies)
- **Issue:** ModelsTab requires CalibrationChart but it hadn't been committed yet.
- **Fix:** Created CalibrationChart.tsx with Nivo ResponsiveScatterPlot, DiagonalLayer custom layer, empty state handling
- **Files modified:** dashboard/src/components/charts/CalibrationChart.tsx (new)
- **Commit:** 8789593

## Self-Check: PASSED

All key files found on disk. Both task commits verified in git log.
- FOUND: dashboard/src/components/shared/ModelComparisonTable.tsx
- FOUND: dashboard/src/components/shared/SignalCard.tsx
- FOUND: dashboard/src/components/charts/CalibrationChart.tsx
- FOUND: dashboard/src/tabs/ModelsTab.tsx
- FOUND: dashboard/src/tabs/SignalsTab.tsx
- FOUND: dashboard/src/__tests__/ModelsTab.test.tsx
- COMMIT 8789593: feat(06-04): build ModelComparisonTable, SignalCard, ModelsTab
- COMMIT b0d66a2: feat(06-03): assemble BacktestTab (includes SignalsTab implementation)
