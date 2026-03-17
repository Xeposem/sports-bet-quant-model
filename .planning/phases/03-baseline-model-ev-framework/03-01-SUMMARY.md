---
phase: 03-baseline-model-ev-framework
plan: 01
subsystem: odds
tags: [odds, devigging, ingestion, csv-parsing, fuzzy-matching, schema]
dependency_graph:
  requires:
    - src/db/schema.sql (matches, players tables)
    - src/db/connection.py (get_connection, _read_schema_sql)
  provides:
    - src/odds/devig.py (power_method_devig)
    - src/odds/ingester.py (parse_tennis_data_csv, upsert_match_odds, manual_entry, import_csv_odds)
    - src/odds/linker.py (fuzzy_link_player, link_odds_to_matches)
    - match_odds table in schema.sql
    - predictions table in schema.sql
  affects:
    - tests/test_loader.py (table count assertions updated)
tech_stack:
  added:
    - scikit-learn>=1.4 (for Phase 3 model training, added to requirements)
    - scipy>=1.10 (brentq root-finding for power method devigging)
    - rapidfuzz>=3.0 (C++ fuzzy string matching for player name linking)
  patterns:
    - scipy.optimize.brentq for numerically stable power method root-finding
    - rapidfuzz token_set_ratio for player name subset matching
    - pandas dayfirst=True for DD/MM/YYYY date parsing
    - INSERT OR REPLACE for idempotent odds upserts
key_files:
  created:
    - src/odds/__init__.py
    - src/odds/devig.py
    - src/odds/ingester.py
    - src/odds/linker.py
    - tests/test_odds.py
  modified:
    - requirements.txt (added scikit-learn, scipy, rapidfuzz)
    - pyproject.toml (added scikit-learn, scipy, rapidfuzz to project.dependencies)
    - src/db/schema.sql (added match_odds and predictions tables)
    - tests/test_loader.py (updated table count assertions to 12)
decisions:
  - "token_set_ratio preferred over token_sort_ratio: token_set_ratio correctly handles subset name variants (Djokovic subset of Novak Djokovic -> 100%), token_sort_ratio gave only 72.7 for the same pair"
  - "Bracket [0.01, 10.0] for brentq instead of research suggested [0.5, 2.0]: wider bracket handles extreme odds without changing behavior for normal cases"
metrics:
  duration_seconds: 328
  completed_date: "2026-03-17"
  tasks_completed: 2
  files_created: 5
  files_modified: 4
---

# Phase 3 Plan 1: Odds Ingestion Pipeline Summary

**One-liner:** Power method devigging via scipy.brentq with tennis-data.co.uk CSV ingestion, rapidfuzz player name linking, and match_odds/predictions schema tables.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for odds module | 1b64433 | tests/test_odds.py |
| 1 (GREEN) | Deps, schema tables, devig module | 5a2abe3 | requirements.txt, pyproject.toml, src/db/schema.sql, src/odds/__init__.py, src/odds/devig.py |
| 2 (GREEN) | Odds ingestion pipeline | 1d8d8de | src/odds/ingester.py, src/odds/linker.py |
| 2 (Fix) | Update table count in test_loader | 8ad6e8d | tests/test_loader.py |

## Verification

All plan verification commands pass:

```
python -m pytest tests/test_odds.py -x -v    -> 21 passed
python -m pytest tests/ -x -q               -> 256 passed (no regressions)
power_method_devig(1.95, 1.95) Sum: 1.000000
match_odds and predictions tables confirmed in schema
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Switched fuzzy scorer from token_sort_ratio to token_set_ratio**
- **Found during:** Task 2 test execution
- **Issue:** `token_sort_ratio` gave score 72.7 for "Novak Djokovic" -> "Djokovic" (below 85 threshold). Plan behavior required score >= 85 for this match.
- **Root cause:** token_sort_ratio alphabetically sorts tokens before comparing — doesn't help when one string is a subset of another. token_set_ratio handles set intersection and achieves 100% for "Djokovic" in "Novak Djokovic".
- **Fix:** Changed `scorer=fuzz.token_sort_ratio` to `scorer=fuzz.token_set_ratio` in `fuzzy_link_player()`. Updated test docstring.
- **Files modified:** src/odds/linker.py, tests/test_odds.py
- **Commit:** 1d8d8de

**2. [Rule 2 - Missing update] Updated test_loader.py table count assertions**
- **Found during:** Full test suite run after Task 2
- **Issue:** `test_schema_creates_all_tables` and `test_db_conn_fixture_has_schema` had hardcoded table counts (10) from Phase 2 that did not include the new match_odds and predictions tables.
- **Fix:** Updated expected table set to include match_odds and predictions; updated count assertion from 10 to 12.
- **Files modified:** tests/test_loader.py
- **Commit:** 8ad6e8d

## Key Implementation Notes

- **Schema FK enforcement:** match_odds uses composite FK (tourney_id, match_num, tour) -> matches, matching the project's established FK pattern
- **Date handling:** CSV parser uses `pd.to_datetime(dayfirst=True, errors='coerce')` then ISO format conversion — handles DD/MM/YYYY without silent failures
- **Odds validation:** Both odds must be >= 1.01 before devigging; brentq bracket [0.01, 10.0] handles extreme favorites safely
- **Idempotency:** upsert_match_odds and manual_entry both use INSERT OR REPLACE consistent with project patterns

## Self-Check: PASSED

Files verified:
- FOUND: src/odds/__init__.py
- FOUND: src/odds/devig.py
- FOUND: src/odds/ingester.py
- FOUND: src/odds/linker.py
- FOUND: tests/test_odds.py

Commits verified:
- FOUND: 1b64433 (test: failing tests)
- FOUND: 5a2abe3 (feat: deps + schema + devig)
- FOUND: 1d8d8de (feat: ingestion pipeline)
- FOUND: 8ad6e8d (fix: test_loader table counts)
