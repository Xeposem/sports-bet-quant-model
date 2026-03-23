---
phase: 10-prizepicks-screenshot-cv-tool-for-automatic-atp-prop-extraction
plan: "02"
subsystem: ui
tags: [react, tanstack-query, typescript, formdata, clipboard, vitest]

# Dependency graph
requires:
  - phase: 10-prizepicks-screenshot-cv-tool-for-automatic-atp-prop-extraction
    provides: POST /props/scan endpoint, PropScanCard/PropScanResponse Pydantic schemas (Plan 01)
  - phase: 08-player-props
    provides: useSubmitPropLine hook, POST /props endpoint, PropsTab component
provides:
  - PropScanCard and PropScanResponse TypeScript interfaces in types.ts
  - useScanPropScreenshot TanStack mutation hook (FormData POST /props/scan)
  - PropScanPreview component with checkbox table and bulk submission
  - PropsTab scan section with file upload button and Ctrl+V clipboard paste
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FormData POST without manual Content-Type header (browser sets multipart boundary)"
    - "Expand backend card.directions array into per-row ScanRow entries on mount"
    - "Clipboard paste via window.addEventListener paste + ClipboardEvent items filter"

key-files:
  created:
    - dashboard/src/components/shared/PropScanPreview.tsx
    - dashboard/src/__tests__/PropScanPreview.test.tsx
  modified:
    - dashboard/src/api/types.ts
    - dashboard/src/hooks/useProps.ts
    - dashboard/src/tabs/PropsTab.tsx
    - dashboard/src/__tests__/PropsTab.test.tsx

key-decisions:
  - "useScanPropScreenshot does NOT set Content-Type header — browser must set multipart boundary automatically for FormData"
  - "PropScanPreview expands card.directions into individual ScanRow entries (one per direction) so users can deselect over/under independently"
  - "PropsTab.test.tsx updated to mock useScanPropScreenshot and PropScanPreview to avoid QueryClient dependency"

patterns-established:
  - "FormData multipart: never set Content-Type manually — let browser handle boundary"
  - "PropScanPreview: expand multi-direction cards into rows, track checked state per row"

requirements-completed:
  - SCAN-03
  - SCAN-04

# Metrics
duration: 7min
completed: 2026-03-23
---

# Phase 10 Plan 02: Frontend Scan Flow Summary

**PrizePicks screenshot scan frontend: file upload + Ctrl+V paste on PropsTab, TanStack FormData mutation, PropScanPreview checkbox table with bulk POST /props submission**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-23T08:11:00Z
- **Completed:** 2026-03-23T08:18:43Z
- **Tasks:** 2 of 3 (Task 3 is human-verify checkpoint)
- **Files modified:** 6

## Accomplishments
- Added PropScanCard and PropScanResponse TypeScript interfaces to api/types.ts
- Created useScanPropScreenshot mutation hook that POSTs FormData to /props/scan without setting Content-Type header
- Created PropScanPreview component: expands multi-direction cards into individual rows, checkbox select/deselect, bulk submission via useSubmitPropLine, toast feedback
- Wired scan flow into PropsTab: Scan section above manual entry form, file upload button, Ctrl+V clipboard paste handler, scan result preview or upload prompt
- 7 unit tests for PropScanPreview all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: TypeScript types, scan mutation hook, PropScanPreview component + tests** - `43d9cee` (feat)
2. **Task 2: Wire scan flow into PropsTab with file upload + clipboard paste** - `33610bf` (feat)

**Plan metadata:** (docs commit — created after checkpoint)

## Files Created/Modified
- `dashboard/src/api/types.ts` - Added PropScanCard and PropScanResponse interfaces
- `dashboard/src/hooks/useProps.ts` - Added useScanPropScreenshot mutation hook
- `dashboard/src/components/shared/PropScanPreview.tsx` - Preview table with checkboxes and bulk submit
- `dashboard/src/__tests__/PropScanPreview.test.tsx` - 7 unit tests covering row rendering, checkbox state, submission
- `dashboard/src/tabs/PropsTab.tsx` - Scan section with file upload button, hidden input, clipboard paste useEffect
- `dashboard/src/__tests__/PropsTab.test.tsx` - Added useScanPropScreenshot mock and PropScanPreview mock

## Decisions Made
- `useScanPropScreenshot` does NOT set `Content-Type` header — browser must set multipart boundary automatically for FormData. Setting it manually causes the server to reject the request.
- `PropScanPreview` expands `card.directions` into individual `ScanRow` entries (one per direction) so users can deselect over/under independently per player.
- `PropsTab.test.tsx` was updated to mock `useScanPropScreenshot` and `PropScanPreview` to avoid QueryClient dependency in tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Updated PropsTab.test.tsx mock to include useScanPropScreenshot**
- **Found during:** Task 2 (verifying all tests pass)
- **Issue:** PropsTab.test.tsx vi.mock for useProps was missing the new useScanPropScreenshot export, causing all 6 PropsTab tests to fail with "[vitest] No useScanPropScreenshot export defined on mock"
- **Fix:** Added useScanPropScreenshot to the vi.mock definition, added import, and added defaultScanMutateData to setupDefaultMocks(). Also added PropScanPreview mock to prevent QueryClient dependency.
- **Files modified:** dashboard/src/__tests__/PropsTab.test.tsx
- **Verification:** npx vitest run — all 80 non-pre-existing tests pass
- **Committed in:** 33610bf (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical test mock)
**Impact on plan:** Necessary fix for test correctness. No scope creep.

## Issues Encountered
- OverviewTab.test.tsx has 4 pre-existing failures (useSimulationResult not mocked — `No QueryClient set`). These were failing before this plan's changes and are out of scope per deviation rules. Logged as pre-existing.

## Next Phase Readiness
- Frontend scan flow complete: upload button, paste handler, preview table, bulk submit
- Task 3 (human-verify checkpoint) requires manual visual verification of the full flow in browser
- Start backend, start frontend, navigate to Props tab, upload data/pp.db._test_sc.png, verify preview table renders, submit selected rows

## Self-Check: PASSED

All files verified present and all commits verified in git log.

---
*Phase: 10-prizepicks-screenshot-cv-tool-for-automatic-atp-prop-extraction*
*Completed: 2026-03-23*
