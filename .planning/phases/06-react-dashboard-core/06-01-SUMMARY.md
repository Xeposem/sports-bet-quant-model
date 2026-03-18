---
phase: 06-react-dashboard-core
plan: "01"
subsystem: frontend
tags: [react, vite, typescript, tailwind, shadcn-ui, nivo, tanstack-query, vitest]
dependency_graph:
  requires: []
  provides:
    - dashboard/src/api/client.ts (typed fetch wrapper)
    - dashboard/src/api/types.ts (TypeScript API interfaces)
    - dashboard/src/providers/QueryProvider.tsx (TanStack Query setup)
    - dashboard/src/components/charts/nivoTheme.ts (dark Nivo theme)
    - dashboard/src/components/layout/Header.tsx (app header)
    - dashboard/src/components/layout/TabNav.tsx (4-tab shell)
    - dashboard/src/App.tsx (app shell)
  affects:
    - All subsequent Phase 6 plans (build on this scaffold)
tech_stack:
  added:
    - Vite 8 + React 19 + TypeScript 5
    - Tailwind CSS 3.4.19 (pinned to v3)
    - shadcn/ui components (table, tabs, card, badge, button, select, skeleton, popover, sonner)
    - TanStack Query v5 (staleTime: Infinity, manual-refresh-only)
    - Lightweight Charts v5.1.0
    - Nivo 0.99.0 (@nivo/bar, @nivo/scatterplot)
    - Vitest 4.1.0 + @testing-library/react
  patterns:
    - typed fetch wrapper with apiFetch<T>
    - QueryProvider wrapping App content
    - darkMode: 'class' + forced dark on <html>
    - Radix Tabs via shadcn/ui
key_files:
  created:
    - dashboard/package.json
    - dashboard/vite.config.ts
    - dashboard/tsconfig.json / tsconfig.app.json / tsconfig.node.json
    - dashboard/tailwind.config.js
    - dashboard/postcss.config.js
    - dashboard/index.html
    - dashboard/components.json
    - dashboard/src/main.tsx
    - dashboard/src/index.css
    - dashboard/vitest.setup.ts
    - dashboard/src/lib/utils.ts
    - dashboard/src/components/ui/ (9 components: button, tabs, card, badge, select, skeleton, popover, sonner, table)
    - dashboard/src/api/client.ts
    - dashboard/src/api/types.ts
    - dashboard/src/providers/QueryProvider.tsx
    - dashboard/src/components/charts/nivoTheme.ts
    - dashboard/src/components/layout/Header.tsx
    - dashboard/src/components/layout/TabNav.tsx
    - dashboard/src/tabs/OverviewTab.tsx
    - dashboard/src/tabs/BacktestTab.tsx
    - dashboard/src/tabs/ModelsTab.tsx
    - dashboard/src/tabs/SignalsTab.tsx
    - dashboard/src/__tests__/App.test.tsx
  modified:
    - dashboard/src/App.tsx (replaced Vite boilerplate)
decisions:
  - "Vitest 4.1.0 requires importing defineConfig from vitest/config (not vite) for test block TypeScript recognition"
  - "shadcn/ui CLI interactive prompt not automatable with -y flag for React 19 peer deps; created all 9 UI component files manually"
  - "Added @testing-library/dom as explicit dev dependency — missing peer dep of @testing-library/react 16"
  - "Added vitest/globals and @testing-library/jest-dom to tsconfig.app.json types for toBeInTheDocument type resolution"
  - "Test 3 (shows Overview tab content by default) uses getByRole(heading) instead of getByText — getByText ambiguous when Overview appears as both tab trigger and tab content heading"
metrics:
  duration_minutes: 11
  tasks_completed: 2
  files_created: 33
  completed_date: "2026-03-18"
---

# Phase 06 Plan 01: React Dashboard Scaffold Summary

React dashboard scaffolded with Vite + TypeScript + Tailwind v3 dark theme, all shadcn/ui components hand-written, typed API client layer with interfaces mirroring all Pydantic schemas, TanStack Query v5 manual-refresh configuration, app shell with 4-tab navigation, and 3 passing smoke tests.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | Scaffold Vite project, install all dependencies, configure Tailwind v3 + shadcn/ui dark theme + test infra | 830852d | Done |
| 2 | Create API client, TypeScript types, QueryProvider, Nivo theme, app shell with Header + TabNav + 4 tab stubs, smoke test | d49098a | Done |

## Verification Results

- `npm run build` exits 0 — no TypeScript errors
- `npx vitest run --reporter=verbose` — 3 passing tests
- Build output: 298.37 kB JS, 15.82 kB CSS
- package.json contains: tailwindcss@^3.4.19, @tanstack/react-query@^5.90.21, lightweight-charts@^5.1.0, @nivo/bar@^0.99.0, vitest@^4.1.0

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing @testing-library/dom peer dependency**
- **Found during:** Task 2 (first vitest run)
- **Issue:** @testing-library/react@16 requires @testing-library/dom but it wasn't installed by npm automatically
- **Fix:** `npm install --legacy-peer-deps -D @testing-library/dom`
- **Files modified:** dashboard/package.json
- **Commit:** d49098a

**2. [Rule 3 - Blocking] vitest/config import required for TypeScript test block recognition**
- **Found during:** Task 1 (build verification)
- **Issue:** Vitest 4.x requires `import { defineConfig } from 'vitest/config'` — using `vite`'s defineConfig doesn't expose the `test` config property to TypeScript
- **Fix:** Changed vite.config.ts to import from `vitest/config`
- **Files modified:** dashboard/vite.config.ts
- **Commit:** 830852d

**3. [Rule 3 - Blocking] shadcn/ui CLI interactive prompt not automatable**
- **Found during:** Task 1 (shadcn init)
- **Issue:** `npx shadcn@2.3.0 add ... -y` shows a React 19 peer dep interactive prompt that doesn't accept the -y flag. The CLI prompts for `--force` or `--legacy-peer-deps`
- **Fix:** Manually created all 9 shadcn/ui component files from scratch (button, tabs, card, badge, select, skeleton, popover, sonner, table) plus lib/utils.ts; installed Radix dependencies directly via `npm install --legacy-peer-deps`
- **Files modified:** dashboard/src/components/ui/*.tsx, dashboard/src/lib/utils.ts
- **Commit:** 830852d

**4. [Rule 1 - Bug] Test 3 used ambiguous getByText('Overview')**
- **Found during:** Task 2 (vitest run)
- **Issue:** 'Overview' appears both as a Radix tab trigger text and as the H2 heading in OverviewTab — getByText throws "multiple elements found"
- **Fix:** Changed test to use `getByRole('heading', { name: 'Overview' })` for unambiguous selection
- **Files modified:** dashboard/src/__tests__/App.test.tsx
- **Commit:** d49098a

**5. [Rule 3 - Blocking] TypeScript type errors for toBeInTheDocument**
- **Found during:** Task 2 (build verification)
- **Issue:** TypeScript didn't recognize jest-dom custom matchers — tsconfig.app.json needed explicit types for vitest/globals and @testing-library/jest-dom
- **Fix:** Added `"vitest/globals"` and `"@testing-library/jest-dom"` to tsconfig.app.json `types` array
- **Files modified:** dashboard/tsconfig.app.json
- **Commit:** d49098a

## Self-Check: PASSED

All key files found on disk. Both task commits verified in git log.
- FOUND: dashboard/src/api/client.ts
- FOUND: dashboard/src/api/types.ts
- FOUND: dashboard/src/providers/QueryProvider.tsx
- FOUND: dashboard/src/components/layout/Header.tsx + TabNav.tsx
- FOUND: dashboard/src/App.tsx
- FOUND: dashboard/vitest.setup.ts + dashboard/components.json
- COMMIT 830852d: chore(06-01): scaffold Vite project
- COMMIT d49098a: feat(06-01): add API client and app shell
