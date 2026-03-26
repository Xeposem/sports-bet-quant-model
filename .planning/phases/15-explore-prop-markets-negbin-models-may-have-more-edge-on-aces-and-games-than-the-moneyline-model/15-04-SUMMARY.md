---
phase: 15-explore-prop-markets-negbin-models-may-have-more-edge-on-aces-and-games-than-the-moneyline-model
plan: 04
subsystem: dashboard-frontend
tags: [react, typescript, nivo, tanstack-query, tabs, props, backtest-analysis]

# Dependency graph
requires:
  - phase: 15-plan-03
    provides: "GET /props/backtest endpoint with PropBacktestResponse schema"
provides:
  - "PropAnalysisTab component with 4 analysis sections (hit rate bars, calibration, rolling line, breakdown table)"
  - "usePropBacktest hook fetching GET /props/backtest"
  - "StatType alias covering all 6 prop stat types"
  - "PropBacktestResponse TypeScript interfaces"
  - "7-tab navigation including prop-analysis tab"
  - "PropsTab expanded to 6 stat type dropdown options"
  - "PMF chart gated for first_set_winner binary stat"
affects:
  - dashboard/src/api/types.ts
  - dashboard/src/hooks/useProps.ts
  - dashboard/src/tabs/PropAnalysisTab.tsx
  - dashboard/src/tabs/PropsTab.tsx
  - dashboard/src/components/layout/TabNav.tsx

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PropAnalysisTab uses usePropBacktest; stat selector filters calibration and rolling charts per stat"
    - "StatType named alias shared across PropPrediction, PropLineEntry, PropScanCard"
    - "first_set_winner binary stat gates PmfChart rendering — shows P% text instead"
    - "@nivo/line ResponsiveLine used for rolling hit rate line chart in PropAnalysisTab"

# Key files
key-files:
  created:
    - dashboard/src/tabs/PropAnalysisTab.tsx
  modified:
    - dashboard/src/api/types.ts
    - dashboard/src/hooks/useProps.ts
    - dashboard/src/tabs/PropsTab.tsx
    - dashboard/src/components/layout/TabNav.tsx

# Decisions
decisions:
  - "StatType named alias added to types.ts and referenced in PropPrediction, PropLineEntry, PropScanCard for DRY 6-value union"
  - "PropAnalysisTab stat selector filters sections 2 (calibration) and 3 (rolling line) but section 1 (bar chart) and section 4 (table) show all stat types"
  - "first_set_winner gated from PmfChart — binary outcome with 2-element PMF renders nonsensically in mu±15 slice; show P(Win 1st Set) text instead"

# Metrics
metrics:
  duration_minutes: 2
  completed_date: "2026-03-26"
  tasks_completed: 2
  files_modified: 5
---

# Phase 15 Plan 04: PropAnalysisTab and Prop Dropdown Expansion Summary

**One-liner:** PropAnalysisTab dashboard tab with hit-rate bar chart, per-stat calibration scatter, rolling hit rate line, and breakdown table; stat type union expanded to 6 values; 7-tab navigation.

## What Was Built

### Task 1: TypeScript types and usePropBacktest hook

Updated `dashboard/src/api/types.ts`:
- Added `export type StatType = 'aces' | 'games_won' | 'double_faults' | 'breaks_of_serve' | 'sets_won' | 'first_set_winner'`
- Updated `PropPrediction.stat_type`, `PropLineEntry.stat_type`, `PropScanCard.stat_type` to reference `StatType`
- Added four new interfaces: `PropBacktestStatRow`, `PropBacktestCalibrationBin`, `PropBacktestRollingRow`, `PropBacktestResponse`

Updated `dashboard/src/hooks/useProps.ts`:
- Added `usePropBacktest` hook using TanStack Query to fetch `/props/backtest` via `apiFetch`
- Imported `PropBacktestResponse` from types

### Task 2: PropAnalysisTab, PropsTab dropdown, TabNav 7th tab

Created `dashboard/src/tabs/PropAnalysisTab.tsx` (163 lines):
- Section 1: Hit rate by stat type bar chart via `@nivo/bar` ResponsiveBar — maps `by_stat_type` to bar data with `STAT_LABELS` labels and 55% edge threshold marker
- Section 2: Per-stat calibration scatter via existing `CalibrationChart` component — filters `calibration_bins` by `selectedStat` and converts to `CalibrationBin[]`
- Section 3: Rolling hit rate line chart via `@nivo/line` ResponsiveLine — filters `rolling_hit_rate` by `selectedStat`
- Section 4: Stat-level breakdown table — columns: Stat Type, Sample Size, Hit Rate (green if >=55%), Avg P(hit), Calibration Score
- Stat selector dropdown (Select component) above sections 2/3 filters both simultaneously
- Loading state shows SkeletonCard; empty state (total_tracked=0) shows EmptyState

Updated `dashboard/src/tabs/PropsTab.tsx`:
- Removed local `type StatType` alias; imports `StatType` from `../api/types`
- Expanded stat type Select to 6 options: aces, games won, double faults, breaks of serve, sets won, first set winner
- Added first_set_winner gate: renders "P(Win 1st Set): XX%" text instead of PmfChart for binary stat

Updated `dashboard/src/components/layout/TabNav.tsx`:
- Added `import { PropAnalysisTab } from '@/tabs/PropAnalysisTab'`
- Added `prop-analysis` TabsTrigger (after Props, before Paper Trading) and matching TabsContent

## Verification

- `npx tsc --noEmit` passes with zero errors after both tasks
- PropAnalysisTab.tsx: 163 lines, exports PropAnalysisTab, contains usePropBacktest, hit_rate, calibration, ResponsiveLine, by_stat_type table
- PropsTab.tsx contains breaks_of_serve, sets_won, first_set_winner dropdown items and first_set_winner PMF gate
- TabNav.tsx contains "prop-analysis" and "PropAnalysisTab" (4 occurrences each)

## Deviations from Plan

None — plan executed exactly as written. RoiBarChart was not used since CalibrationChart already handles its section and a simple inline ResponsiveBar suffices for the hit rate chart (avoiding tight coupling to ROI-specific labeling).

## Known Stubs

None — PropAnalysisTab is fully wired to usePropBacktest which calls the live GET /props/backtest endpoint.

## Self-Check: PASSED

- `dashboard/src/tabs/PropAnalysisTab.tsx` exists: confirmed (163 lines)
- `dashboard/src/hooks/useProps.ts` contains usePropBacktest: confirmed
- `dashboard/src/api/types.ts` contains StatType and PropBacktestResponse: confirmed
- `dashboard/src/components/layout/TabNav.tsx` contains prop-analysis: confirmed
- Task 1 commit `d76340b`: confirmed
- Task 2 commit `2ca6e1c`: confirmed
- TypeScript check passes with zero errors: confirmed
