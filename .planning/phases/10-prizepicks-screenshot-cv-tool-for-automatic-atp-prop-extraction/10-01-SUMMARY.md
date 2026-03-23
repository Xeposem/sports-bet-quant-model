---
phase: 10-prizepicks-screenshot-cv-tool-for-automatic-atp-prop-extraction
plan: "01"
subsystem: props-ocr
tags: [ocr, scanner, fastapi, pytesseract, opencv, rapidfuzz, pydantic]
dependency_graph:
  requires:
    - src/props/base.py
    - src/api/routers/props.py
    - src/api/schemas.py
    - database players table (ATP tour filter)
  provides:
    - src/props/scanner.py (scan_image_bytes entry point + full OCR pipeline)
    - POST /props/scan endpoint
    - PropScanCard and PropScanResponse Pydantic schemas
  affects:
    - src/api/routers/props.py (new route added)
    - requirements.txt (3 new dependencies)
tech_stack:
  added:
    - pytesseract==0.3.13
    - opencv-python>=4.10.0
    - python-multipart>=0.0.20
  patterns:
    - Separator-band card segmentation with equal-division fallback
    - pytesseract --psm 6 per-card OCR
    - rapidfuzz token_set_ratio ATP player fuzzy matching
    - asyncio.to_thread for sync OCR function in async FastAPI endpoint
    - TDD Red-Green cycle with private function unit tests
key_files:
  created:
    - src/props/scanner.py
    - tests/test_props_scanner.py
  modified:
    - requirements.txt
    - src/api/schemas.py
    - src/api/routers/props.py
decisions:
  - "TesseractNotFoundError returns status=tesseract_not_found dict (not exception) inside scan_image_bytes, converted to HTTP 503 at endpoint level"
  - "Empty card guard in _ocr_card prevents cv2.cvtColor crash on zero-size slices from small fallback images"
  - "POST /scan registered before POST '' in props.py router — same pattern as GET /accuracy before GET ''"
  - "opencv-python added to requirements.txt — was installed in venv but not declared (deviation Rule 2)"
  - "TesseractNotFoundError() takes no args in pytesseract 0.3.13 — test corrected from TesseractNotFoundError('not found') to TesseractNotFoundError()"
metrics:
  duration_seconds: 575
  completed_date: "2026-03-23"
  tasks_completed: 2
  files_modified: 5
  tests_added: 26
---

# Phase 10 Plan 01: OCR Scanner Backend + POST /props/scan Summary

OCR pipeline with pytesseract card segmentation, noise-tolerant parsing, rapidfuzz ATP player matching, and FastAPI multipart upload endpoint.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (TDD RED) | Failing scanner tests | 7fe4e93 | tests/test_props_scanner.py |
| 1 (TDD GREEN) | Scanner module + schemas + dependency | 314bf37 | requirements.txt, src/props/scanner.py, src/api/schemas.py, tests/test_props_scanner.py |
| 2 | POST /props/scan endpoint wired | 84c71e6 | src/api/routers/props.py, tests/test_props_scanner.py |

## What Was Built

**`src/props/scanner.py`** — Full OCR pipeline:
- `_find_separator_bands`: detects near-black (< 10 brightness) separator bands in 1D brightness profiles
- `_segment_cards`: separator-based grid segmentation with 4x5 equal-division fallback
- `_extract_player_name`: primary `"Name - Player"` regex + secondary 2-word capitalized fallback for cards without marker
- `_extract_line_value`: STAT_PATTERNS keyword matching with half-point preference in 3-35 range; handles OCR noise like "toraicameswon"
- `_extract_directions`: "Less"/"More" detection defaulting to both when absent
- `_load_player_names`: ATP player dict from SQLite `players` table
- `_fuzzy_match_player`: rapidfuzz token_set_ratio with threshold=80, silently excludes non-ATP players
- `_ocr_card`: per-card PIL+pytesseract OCR with --psm 6 and empty-card guard
- `scan_image_bytes`: public entry point with TesseractNotFoundError graceful handling

**`src/api/schemas.py`** additions: `PropScanCard` and `PropScanResponse` Pydantic models.

**`src/api/routers/props.py`** addition: `POST /scan` endpoint before `POST ""`, with content_type validation, asyncio.to_thread offloading, and 503 for missing Tesseract.

**`tests/test_props_scanner.py`**: 26 tests covering all parsing functions + scan_image_bytes error paths + endpoint integration (mocked scanner).

## Test Results

```
26 passed in 4.08s
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing dependency] Added opencv-python to requirements.txt**
- **Found during:** Task 1 implementation
- **Issue:** opencv-python was installed in venv but not declared in requirements.txt — a correctness requirement for the scanner module to work in fresh environments
- **Fix:** Added `opencv-python>=4.10.0` to requirements.txt between pytesseract and python-multipart
- **Files modified:** requirements.txt
- **Commit:** 314bf37

**2. [Rule 1 - Bug] TesseractNotFoundError takes no constructor arguments**
- **Found during:** Task 1 test RED phase
- **Issue:** Test used `pytesseract.TesseractNotFoundError("not found")` but the class takes no positional arguments in pytesseract 0.3.13
- **Fix:** Changed to `pytesseract.TesseractNotFoundError()` in test
- **Files modified:** tests/test_props_scanner.py
- **Commit:** 314bf37

**3. [Rule 1 - Bug] Empty card guard in _ocr_card**
- **Found during:** Task 1 test GREEN phase (test_valid_tiny_image_tesseract_not_found)
- **Issue:** A 50x50 white PNG produces empty card slices via fallback grid segmentation; cv2.cvtColor crashes on zero-size array
- **Fix:** Added early return None if `card_img.size == 0 or card_img.shape[0] < 2 or card_img.shape[1] < 2`
- **Files modified:** src/props/scanner.py
- **Commit:** 314bf37

**4. [Rule 1 - Bug] Custom error response format in endpoint rejection test**
- **Found during:** Task 2 integration test
- **Issue:** App uses custom error format `{"error": ..., "message": ...}` not standard `{"detail": ...}`; test expected "detail" key
- **Fix:** Updated test to check both `detail` and `message` keys
- **Files modified:** tests/test_props_scanner.py
- **Commit:** 84c71e6

## Pre-existing Failures (Out of Scope)

The following test failures existed before this plan and were not caused by these changes (verified via git stash):
- `tests/test_model_bayesian.py` — `ModuleNotFoundError: No module named 'arviz'`
- `tests/test_api.py::TestPropsStub::test_props_stub` — stale test expecting old `"not_available"` stub response
- `tests/test_backtest.py::TestBacktestSchema::test_table_count_includes_backtest_tables` — pre-existing schema mismatch
- `tests/test_loader.py::test_schema_creates_all_tables` — pre-existing schema mismatch
- `tests/test_props.py::test_games_won_uses_score_parser` and `test_predict_and_store` — pre-existing `no such table: tournaments`

## Self-Check: PASSED

- FOUND: src/props/scanner.py
- FOUND: tests/test_props_scanner.py
- FOUND: 7fe4e93 test(10-01): add failing tests for scanner module parsing functions
- FOUND: 314bf37 feat(10-01): scanner module + Pydantic schemas + pytesseract dependency
- FOUND: 84c71e6 feat(10-01): POST /props/scan endpoint wired into FastAPI router
