---
phase: 06-react-dashboard-core
plan: 05
subsystem: ui
tags: [react, typescript, tanstack-query, vitest, sonner, radix-ui, error-boundary]

# Dependency graph
requires:
  - phase: 06-react-dashboard-core
    provides: "All 4 tab components (Overview, Backtest, Models, Signals) built in plans 02-04"
provides:
  - "useRefreshAll hook — POST /refresh with polling and query invalidation"
  - "Header refresh button with spinner and toast error state"
  - "ErrorBoundary wrapping TabNav for render error recovery"
  - "Bankroll date-click popover showing bets on selected date"
  - "Consistent loading/error/empty states across all tabs"
  - "Complete integrated dashboard verified end-to-end"
affects: [07-advanced-models, 08-props-system, 09-paper-trading]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "useMutation with setInterval polling for async job completion"
    - "Class-component ErrorBoundary with getDerivedStateFromError + componentDidCatch"
    - "Toast error notification via sonner on mutation failure"
    - "Query invalidation (invalidateQueries) on refresh success triggers all active tab re-fetches"

key-files:
  created:
    - dashboard/src/hooks/useRefresh.ts
    - dashboard/src/components/shared/ErrorBoundary.tsx
    - dashboard/src/__tests__/useRefresh.test.tsx
  modified:
    - dashboard/src/components/layout/Header.tsx
    - dashboard/src/tabs/OverviewTab.tsx
    - dashboard/src/tabs/SignalsTab.tsx
    - dashboard/src/App.tsx
    - dashboard/src/__tests__/App.test.tsx

key-decisions:
  - "useRefreshAll polls /refresh/{job_id} every 2 seconds via setInterval until status=complete or error — simple interval loop avoids extra library dependency"
  - "ErrorBoundary wraps TabNav only (not Header) so header controls remain usable during render error recovery"
  - "Bankroll date popover anchored below chart using OverviewTab local state (clickedDate) — no global state needed for single-chart interaction"

patterns-established:
  - "Pattern 1: Async job polling — useMutation wraps POST + polling Promise resolving on job completion"
  - "Pattern 2: Error boundary scope — wrap content areas, not navigation/header, for graceful degradation"
  - "Pattern 3: Refresh invalidation — queryClient.invalidateQueries() with no args re-fetches all active queries after data refresh"

requirements-completed: [DASH-01, DASH-02, DASH-03, DASH-05, DASH-06]

# Metrics
duration: ~20min
completed: 2026-03-18
---

# Phase 6 Plan 05: Dashboard Integration and Refresh Flow Summary

**useRefreshAll hook with POST /refresh polling + ErrorBoundary + bankroll date popover wiring the complete integrated dashboard**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-03-18
- **Completed:** 2026-03-18
- **Tasks:** 2 (1 auto + 1 human-verify checkpoint approved)
- **Files modified:** 8

## Accomplishments
- Implemented useRefreshAll hook with setInterval polling against /refresh/{job_id} and queryClient.invalidateQueries() on success
- Wired Header refresh button with Loader2 spinner, "Refreshing..." text, aria-disabled, and sonner toast on error
- Created class-based ErrorBoundary with getDerivedStateFromError/componentDidCatch wrapping TabNav in App.tsx
- Connected bankroll date-click popover in OverviewTab showing bet details for selected date
- Updated SignalsTab empty state action button to trigger useRefreshAll mutation
- Visual verification approved by user: all 4 tabs, refresh flow, dark theme, and interactive features confirmed

## Task Commits

Each task was committed atomically:

1. **Task 1: Create useRefresh hook, wire Header, add ErrorBoundary, bankroll popover, update tabs** - `fccded3` (feat)
2. **Task 2: Visual verification checkpoint** - approved by user (no code commit — verification only)

## Files Created/Modified
- `dashboard/src/hooks/useRefresh.ts` - useMutation with POST /refresh + polling + invalidateQueries
- `dashboard/src/components/shared/ErrorBoundary.tsx` - Class ErrorBoundary with getDerivedStateFromError, componentDidCatch, retry button
- `dashboard/src/components/layout/Header.tsx` - Refresh button with spinner, aria-disabled, toast on error
- `dashboard/src/tabs/OverviewTab.tsx` - Bankroll date-click popover wired, clickedDate state
- `dashboard/src/tabs/SignalsTab.tsx` - Empty state action button wires to useRefreshAll
- `dashboard/src/App.tsx` - ErrorBoundary wrapping TabNav
- `dashboard/src/__tests__/useRefresh.test.tsx` - Tests: POST call, polling until complete, query invalidation
- `dashboard/src/__tests__/App.test.tsx` - Tests: ErrorBoundary in tree, Toaster mounted

## Decisions Made
- useRefreshAll polls every 2 seconds using setInterval inside a Promise — avoids adding a dedicated polling library for a single use case
- ErrorBoundary wraps TabNav only, not Header, so the refresh button and navigation remain functional when tab content throws a render error
- Bankroll date popover uses OverviewTab local state (clickedDate) rather than global state — single-chart interaction does not warrant global state complexity

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 06 React Dashboard Core is complete — all 5 plans executed and verified
- Dashboard connects to FastAPI backend and all 4 tabs render with live data, loading, and error states
- Ready for Phase 07 (Advanced Models) or Phase 08 (Props System) — dashboard will surface new model outputs without changes to the shell

---
*Phase: 06-react-dashboard-core*
*Completed: 2026-03-18*
