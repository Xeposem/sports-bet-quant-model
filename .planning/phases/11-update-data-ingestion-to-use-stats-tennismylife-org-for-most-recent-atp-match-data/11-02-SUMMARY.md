---
phase: 11-update-data-ingestion-to-use-stats-tennismylife-org-for-most-recent-atp-match-data
plan: "02"
subsystem: ingestion
tags: [tml, ingestion, loader, cli, tdd]
dependency_graph:
  requires: ["11-01"]
  provides: ["TML-03", "TML-04", "TML-05"]
  affects: ["src/ingestion/loader.py", "src/ingestion/__main__.py"]
tech_stack:
  added: []
  patterns: ["TDD red-green", "source-dispatch", "HTTPError fallback", "argparse choices"]
key_files:
  created:
    - tests/test_loader_tml.py
    - tests/test_ingestion_cli.py
  modified:
    - src/ingestion/loader.py
    - src/ingestion/__main__.py
decisions:
  - "ingest_year_tml reads winner_id/loser_id as str dtype then casts to Int64 after normalise_tml_dataframe — avoids ValueError on alphanumeric TML IDs"
  - "auto mode catches requests.exceptions.HTTPError (not generic Exception) for precise Sackmann 404 detection without masking TML errors"
  - "ATP_Database.csv re-use check: player_csv already present skips re-download — idempotent multi-year runs"
  - "os import moved to module level in loader.py (was previously import os inside ingest_year_tml stub) — consistent with project style"
metrics:
  duration_minutes: 4
  completed_date: "2026-03-23"
  tasks_completed: 2
  files_modified: 4
---

# Phase 11 Plan 02: Wire TML Adapter into Ingestion Pipeline Summary

TML ingestion wired end-to-end: `ingest_year_tml` integrates Plan 01 downloader and ID mapper into the existing loader pipeline, and `--source {sackmann,tml,auto}` CLI flag controls data source selection.

## Tasks Completed

### Task 1: Add ingest_year_tml to loader.py + source-aware ingest_all (TDD)

**RED commit:** `bd1530e` — 5 failing tests for ingest_year_tml and ingest_all source dispatch

**GREEN commit:** `219079a` — Implementation passes all 5 tests

**Changes to `src/ingestion/loader.py`:**
- Added module-level imports: `os`, `requests`, `download_tml_match_file`, `download_tml_player_file`, `build_id_map`, `normalise_tml_dataframe`
- Added `ingest_year_tml(conn, year, raw_dir, force=False) -> dict` — full pipeline: TML CSV download, ATP_Database.csv download (if missing), ID map build, read CSV with str IDs, normalise to Int64, clean, upsert (tournaments/players/matches/stats), log, commit
- Updated `ingest_all` signature: added `source: str = "auto"` parameter
- Updated `ingest_all` body: dispatches to `ingest_year_tml` (tml mode), `ingest_year` (sackmann mode), or auto-detects (tries Sackmann, catches `requests.exceptions.HTTPError`, falls back to TML)
- Existing `ingest_year` function is completely unchanged

**Tests created (`tests/test_loader_tml.py`, 230 lines, 5 tests):**
- `test_ingest_year_tml_inserts_matches` — verifies winner_id >= 900000
- `test_ingest_year_tml_player_ids_are_integers` — verifies `typeof(winner_id)` = 'integer' in DB
- `test_ingest_year_tml_logs_tml_source` — verifies source_file contains "tml_"
- `test_ingest_all_auto_falls_back_to_tml` — mocks HTTPError on Sackmann, verifies TML called
- `test_ingest_all_sackmann_mode_unchanged` — verifies TML functions never called in sackmann mode

### Task 2: Add --source CLI flag + CLI tests

**Commit:** `3d356f5`

**Changes to `src/ingestion/__main__.py`:**
- Updated module docstring with TML usage examples
- Added `--source {sackmann,tml,auto}` argument to `_build_parser()` after `--force`, default `"auto"`
- Updated `ingest_all` call in `main()` to pass `source=args.source`
- Updated startup print statement to include `source={args.source}`

**Tests created (`tests/test_ingestion_cli.py`, 90 lines, 6 tests):**
- `test_source_flag_default_is_auto` — default when omitted
- `test_source_flag_accepts_tml` — --source tml
- `test_source_flag_accepts_sackmann` — --source sackmann
- `test_source_flag_accepts_auto` — --source auto
- `test_source_flag_rejects_invalid` — raises SystemExit
- `test_main_passes_source_to_ingest_all` — verifies source kwarg forwarded

## Verification Results

```
python -m pytest tests/test_loader_tml.py tests/test_ingestion_cli.py -v
11 passed in 0.55s

python -m src.ingestion --help
  --source {sackmann,tml,auto}
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `tests/test_loader_tml.py` — file exists, 5 tests pass
- [x] `tests/test_ingestion_cli.py` — file exists, 6 tests pass
- [x] `src/ingestion/loader.py` contains `def ingest_year_tml(`
- [x] `src/ingestion/loader.py` contains `from src.ingestion.tml_downloader import download_tml_match_file, download_tml_player_file`
- [x] `src/ingestion/loader.py` contains `from src.ingestion.tml_id_mapper import build_id_map, normalise_tml_dataframe`
- [x] `src/ingestion/loader.py` contains `source="auto"` in ingest_all signature
- [x] `src/ingestion/loader.py` contains `tml_dtypes["winner_id"] = str`
- [x] `src/ingestion/__main__.py` contains `"--source"` and `choices=["sackmann", "tml", "auto"]`
- [x] Commits: bd1530e (test RED), 219079a (feat GREEN), 3d356f5 (feat task2)

## Self-Check: PASSED
