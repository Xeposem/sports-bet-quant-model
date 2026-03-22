---
phase: 09-simulation-signals-paper-trading
plan: "03"
subsystem: frontend
tags: [signals, paper-trading, react, typescript, vitest, lightweight-charts]
dependency_graph:
  requires: ["09-01"]
  provides: ["SignalCard", "SignalsTab", "PaperTradingTab", "usePaperTrading", "useSignals"]
  affects: ["dashboard/src/components/layout/TabNav.tsx"]
tech_stack:
  added: []
  patterns:
    - TanStack Query useMutation for paper bet placement and signal status updates
    - localStorage-persisted EV threshold slider in SignalsTab
    - Lightweight Charts LineSeries for paper equity curve (matches BankrollChart pattern)
    - inline dim/hide mode toggle for EV threshold filtering
key_files:
  created:
    - dashboard/src/hooks/usePaperTrading.ts
    - dashboard/src/tabs/PaperTradingTab.tsx
    - dashboard/src/__tests__/SignalCard.test.tsx
    - dashboard/src/__tests__/PaperTradingTab.test.tsx
  modified:
    - dashboard/src/api/types.ts
    - dashboard/src/hooks/useSignals.ts
    - dashboard/src/components/shared/SignalCard.tsx
    - dashboard/src/tabs/SignalsTab.tsx
    - dashboard/src/components/layout/TabNav.tsx
    - dashboard/src/__tests__/SignalsTab.test.tsx
decisions:
  - "PaperEquityChart uses LineSeries (not BaselineSeries) since paper equity has no reference baseline — green/red color determined by total_pnl sign"
  - "SignalsTab dim/hide toggle defaults to dim mode — hides cards only when toggle is explicitly set to Hide"
  - "PaperTradingTab bet history sorted by placed_at descending; pagination is 20 rows per page"
  - "useUpdateSignalStatus and usePlacePaperBet imported directly in SignalsTab for inline callbacks with toast feedback"
metrics:
  duration_seconds: 448
  completed_date: "2026-03-22"
  tasks_completed: 3
  files_created: 4
  files_modified: 6
---

# Phase 9 Plan 03: Signals + Paper Trading Frontend Summary

**One-liner:** Enhanced SignalCard with status/confidence/Sharpe/stake/Place Bet, SignalsTab EV threshold slider with localStorage, PaperTradingTab with 3-state session management and inline bet resolution, 6th TabNav tab wired.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Signal + Paper Trading types and hooks | ecc3d46 | types.ts (+SignalRecord/PaperSession/PaperBet/PaperEquityResponse), useSignals.ts, usePaperTrading.ts |
| 2 | Enhanced SignalCard + SignalsTab with threshold slider | 384482f | SignalCard.tsx, SignalsTab.tsx, SignalCard.test.tsx, SignalsTab.test.tsx |
| 3 | PaperTradingTab + TabNav wiring + tests | d759196 | PaperTradingTab.tsx, TabNav.tsx, PaperTradingTab.test.tsx |

## What Was Built

### Task 1 — Types and Hooks
- Appended `SignalRecord`, `SignalsResponse`, `PaperSession`, `PaperBet`, `PaperBetsResponse`, `PaperEquityPoint`, `PaperEquityResponse` to `types.ts`
- Rewrote `useSignals` to use `/signals` endpoint (not `/predict`), accepts `status` param, adds `useUpdateSignalStatus` mutation
- Created `usePaperTrading.ts` with 7 exports: `usePaperSession`, `useStartSession`, `useResetSession`, `usePaperBets`, `usePlacePaperBet`, `useResolveBet`, `usePaperEquity`

### Task 2 — SignalCard + SignalsTab
- Rewrote `SignalCard` from `PredictionRow` to `SignalRecord` type
- Added status badge (green/slate/blue/slate with line-through per status), confidence %, Sharpe (2dp), stake ($XX.XX), Place Bet button (disabled when no paper session with tooltip), Mark Acted On button (hidden for expired/acted-on)
- Added `dimmed` prop: `opacity-50 pointer-events-none` class
- Updated `SignalsTab` with EV threshold slider (range 0-20 step 0.1), `localStorage.setItem('ev_threshold')` persistence, dim/hide toggle, `usePaperSession` for `paperSessionActive`, `usePlacePaperBet` and `useUpdateSignalStatus` for inline actions with toast feedback
- 10 SignalCard tests + 7 SignalsTab tests (all pass)

### Task 3 — PaperTradingTab + TabNav
- Created `PaperTradingTab` with 3 states:
  - **State A (no session):** EmptyState + bankroll input + Start Session button
  - **State B (active, no bets):** KPI row (Bankroll/P&L/Win Rate/Bets) + EmptyState
  - **State C (active, bets):** KPI row + Lightweight Charts equity curve (green/red by P&L sign) + bet history table with Pending badges, inline Win/Loss resolution buttons, pagination (20/page)
- Reset Session uses `window.confirm` guard
- Updated `TabNav` to add 6th "Paper Trading" tab (trigger + content), imports `PaperTradingTab`
- 10 PaperTradingTab tests (all pass)

## Test Results

| Test File | Tests | Status |
|-----------|-------|--------|
| SignalCard.test.tsx | 10 | PASSED |
| PaperTradingTab.test.tsx | 10 | PASSED |
| SignalsTab.test.tsx | 7 | PASSED |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] SignalsTab existing test had getByText(/min ev/i) matching multiple elements**
- **Found during:** Task 2 test run
- **Issue:** After adding the EV threshold slider annotation ("Min EV: 0.0%"), the existing test `getByText(/min ev/i)` matched both the FilterBar "Min EV" label and the slider annotation, causing "multiple elements found" error
- **Fix:** Changed `getByText` to `getAllByText` with `length > 0` assertion in updated SignalsTab test
- **Files modified:** dashboard/src/__tests__/SignalsTab.test.tsx

**2. [Rule 1 - Bug] types.ts was not included in Task 1 commit**
- **Found during:** Task 1 commit
- **Issue:** `git add dashboard/src/api/types.ts` did not include the types.ts changes in the ecc3d46 commit because the file had already been modified and committed by the 09-04 plan in a prior session. The Signal/Paper types were already present in the file from the e18a277 commit.
- **Fix:** No action needed — types were verified in-place using `git log --all -- dashboard/src/api/types.ts` and `grep SignalRecord`. The types are correct and fully committed.

## Self-Check: PASSED
