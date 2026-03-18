---
phase: 06-react-dashboard-core
plan: "03"
subsystem: dashboard
tags: [react, nivo, charts, backtest, filtering, pagination, vitest]
dependency_graph:
  requires: ["06-01", "06-02"]
  provides: ["BacktestTab", "RoiBarChart", "FilterBar", "FilterChip", "BetHistoryTable"]
  affects: ["dashboard/src/tabs/BacktestTab.tsx"]
tech_stack:
  added: []
  patterns:
    - Nivo ResponsiveBar horizontal layout with dynamic color (positive=green, negative=red, active=blue)
    - Radix Select with __all__ sentinel for empty-value filtering (value="" disallowed by Radix)
    - Click-to-filter toggle pattern with setChartFilter state in parent tab
    - Page-based pagination (page * limit = offset) for TanStack Query hooks
key_files:
  created:
    - dashboard/src/components/charts/RoiBarChart.tsx
    - dashboard/src/components/shared/FilterBar.tsx
    - dashboard/src/components/shared/FilterChip.tsx
    - dashboard/src/components/shared/BetHistoryTable.tsx
    - dashboard/src/__tests__/RoiBarChart.test.tsx
    - dashboard/src/__tests__/BacktestTab.test.tsx
  modified:
    - dashboard/src/tabs/BacktestTab.tsx
    - dashboard/src/components/charts/CalibrationChart.tsx
decisions:
  - "Radix Select disallows value='' — used __all__ sentinel string, converted back to '' on change"
  - "CalibrationChart layers type error fixed with 'as any' cast — Nivo's ScatterPlotCustomSvgLayer type is incompatible with direct function reference"
  - "Test uses getAllByText for Surface/Year/Model — these labels appear in both FilterBar and BetHistoryTable header"
metrics:
  duration_minutes: 7
  completed_date: "2026-03-18"
  tasks_completed: 2
  files_created: 6
  files_modified: 2
---

# Phase 06 Plan 03: Backtest Tab — ROI Charts, Filter Bar, Bet History Table Summary

**One-liner:** Full Backtest tab with 5 Nivo horizontal ROI bar charts, click-to-filter state, dismissible FilterChip, FilterBar dropdowns, and paginated BetHistoryTable — all typed, styled per UI-SPEC, with tests passing.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Build RoiBarChart, FilterBar, FilterChip, BetHistoryTable | 1ff8215 | RoiBarChart.tsx, FilterBar.tsx, FilterChip.tsx, BetHistoryTable.tsx |
| 2 | Assemble BacktestTab with click-to-filter, tests | b0d66a2 | BacktestTab.tsx, RoiBarChart.test.tsx, BacktestTab.test.tsx |

## What Was Built

### RoiBarChart (`dashboard/src/components/charts/RoiBarChart.tsx`)
- Nivo ResponsiveBar with `layout="horizontal"`, `role="img"`, `aria-label="ROI by {dimension}"`
- Dynamic color: active filter bar = blue-400, positive ROI = green-500, negative ROI = red-500
- Custom dark tooltip showing dimension value and ROI percentage
- `onClick` forwards to parent via `onBarClick(String(bar.indexValue))`

### FilterBar (`dashboard/src/components/shared/FilterBar.tsx`)
- Accepts array of filter definitions with key, label, options, value, onChange
- Radix Select dropdowns with `__all__` sentinel for "All" option (Radix disallows `value=""`)
- Dark styling per UI-SPEC: bg-slate-800, border-slate-700, uppercase tracking-wider labels

### FilterChip (`dashboard/src/components/shared/FilterChip.tsx`)
- Dismissible pill: "Filtered by:" prefix + label + X button
- `aria-label="Remove {label} filter"` per accessibility contract

### BetHistoryTable (`dashboard/src/components/shared/BetHistoryTable.tsx`)
- shadcn Table with paginated rows (20 per page), Prev/Next buttons
- EV% and P&L colored green-500 (positive) / red-500 (negative)
- Loading: SkeletonCard variant="table"; Empty: "No backtest results" EmptyState
- "Showing {start}–{end} of {total} bets" pagination footer

### BacktestTab (`dashboard/src/tabs/BacktestTab.tsx`)
- 5 ROI charts in 2x2 grid + full-width Rank Tier chart
- `chartFilter: { dimension, value } | null` — toggle behavior (click same bar clears filter)
- `filterParams` state drives `useBacktestSummary` and merged into `useBacktestBets` via `buildBetsFilterObject`
- FilterBar with surface (hardcoded), year (from summary data), model dropdowns
- FilterChip shown when chartFilter active; dismiss resets chartFilter + page

## Verification Results

- `npm run build`: zero TypeScript errors, built in 2.20s
- `npx vitest run`: 30/30 tests passed across 8 test files
- All 5 acceptance criteria for Task 1 confirmed present via grep
- All 9 acceptance criteria for Task 2 confirmed present via grep and test output

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing CalibrationChart layers type error blocking build**
- **Found during:** Task 1 verification (`npm run build`)
- **Issue:** `CalibrationChart.tsx` line 62 used `Parameters<typeof ResponsiveScatterPlot>[0]['layers'][number]` type assertion that TypeScript rejected with TS2537
- **Fix:** Replaced with `as any` cast with eslint-disable comment
- **Files modified:** `dashboard/src/components/charts/CalibrationChart.tsx`
- **Commit:** 1ff8215

**2. [Rule 1 - Bug] Radix Select disallows value="" for SelectItem**
- **Found during:** Task 2 test run
- **Issue:** `FilterBar` used `<SelectItem value="">All</SelectItem>` which throws "A `<Select.Item />` must have a value prop that is not an empty string"
- **Fix:** Changed "All" option to use `value="__all__"` sentinel; `onValueChange` converts `__all__` → `""` before calling parent's `onChange`
- **Files modified:** `dashboard/src/components/shared/FilterBar.tsx`
- **Commit:** b0d66a2

**3. [Rule 1 - Bug] Test used getByText for labels that appear in multiple elements**
- **Found during:** Task 2 test run
- **Issue:** "Surface", "Year", "Model" appear in both FilterBar labels and BetHistoryTable header cells
- **Fix:** Changed `getByText` to `getAllByText(...).length >= 1` assertions
- **Files modified:** `dashboard/src/__tests__/BacktestTab.test.tsx`
- **Commit:** b0d66a2

## Self-Check

Files verified:
- `dashboard/src/components/charts/RoiBarChart.tsx` — FOUND
- `dashboard/src/components/shared/FilterBar.tsx` — FOUND
- `dashboard/src/components/shared/FilterChip.tsx` — FOUND
- `dashboard/src/components/shared/BetHistoryTable.tsx` — FOUND
- `dashboard/src/tabs/BacktestTab.tsx` — FOUND
- `dashboard/src/__tests__/RoiBarChart.test.tsx` — FOUND
- `dashboard/src/__tests__/BacktestTab.test.tsx` — FOUND

Commits verified:
- 1ff8215 — FOUND
- b0d66a2 — FOUND

## Self-Check: PASSED
