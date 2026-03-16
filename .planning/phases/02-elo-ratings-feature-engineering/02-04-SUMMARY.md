---
phase: 02-elo-ratings-feature-engineering
plan: "04"
subsystem: features-integration
tags: [feature-builder, refresh-pipeline, apscheduler, integration, tdd, look-ahead-bias]

dependency_graph:
  requires:
    - src/ratings/glicko.py (compute_all_ratings)
    - src/features/h2h.py (get_h2h)
    - src/features/form.py (compute_rolling_form)
    - src/features/ranking.py (get_ranking_features)
    - src/features/fatigue.py (get_fatigue_features)
    - src/features/tourney.py (encode_tourney_level)
    - src/sentiment/scorer.py (weighted_player_sentiment)
    - src/sentiment/store.py (get_player_articles)
    - src/sentiment/fetcher.py (fetch_all_articles)
    - src/ingestion/loader.py (ingest_all)
  provides:
    - src/features/builder.py (build_feature_row, build_all_features)
    - src/refresh/runner.py (refresh_all)
    - src/refresh/scheduler.py (build_scheduler)
  affects:
    - match_features table (populated with complete feature matrix)
    - Phase 3 baseline logistic regression model (consumes match_features)
    - Phase 5 FastAPI (imports build_scheduler for lifespan startup)

tech_stack:
  added:
    - apscheduler==3.11.2 (BackgroundScheduler + CronTrigger for daily refresh)
  patterns:
    - Wide feature assembly: one flat dict per (player, match) combining all subsystems
    - INSERT OR REPLACE for idempotent build_all_features re-runs
    - Fault-tolerant pipeline: each refresh step in try/except, failures logged but pipeline continues
    - Lazy sentiment import in build_feature_row: graceful None when articles missing
    - Scheduler returned NOT-started — caller starts it (Phase 5 FastAPI lifespan pattern)

key_files:
  created:
    - src/features/builder.py
    - src/refresh/__init__.py
    - src/refresh/runner.py
    - src/refresh/scheduler.py
    - src/refresh/__main__.py
    - tests/test_builder.py
    - tests/test_refresh.py
  modified:
    - requirements.txt (added apscheduler>=3.10.0)
    - pyproject.toml (added apscheduler>=3.10.0 to dependencies)

decisions:
  - "INSERT OR REPLACE (not ON CONFLICT DO UPDATE) for match_features idempotency — simpler syntax, same semantics for this use case"
  - "Sentiment in build_feature_row uses try/except rather than None-guarding — tables may not exist in early pipeline stages"
  - "build_scheduler returns NOT-started scheduler — caller controls lifecycle, consistent with FastAPI lifespan pattern (Phase 5)"
  - "refresh_all uses module-level imports (not lazy) for ingest_all/compute_all_ratings/build_all_features to allow patching at module scope in tests"
  - "Sentiment step skipped entirely (not just article scoring) when fetch_articles=False for faster refresh cycles"

metrics:
  duration_seconds: 424
  completed_date: "2026-03-16"
  tasks_completed: 3
  files_created: 7
  files_modified: 2
---

# Phase 2 Plan 4: Feature Builder and Refresh Pipeline Summary

**One-liner:** Complete feature matrix assembly from Glicko-2 ratings, H2H, rolling form, ranking, fatigue, and sentiment into match_features table, with a fault-tolerant daily refresh pipeline and APScheduler wrapper.

## What Was Built

### Feature Builder (Task 1)

`src/features/builder.py`:

- `_get_player_elo(conn, player_id, before_date)`: queries player_elo for all 4 surface tracks with strict `as_of_date < before_date` cutoff. Returns defaults (1500, 350) for surfaces with no prior snapshot.

- `build_feature_row(conn, match, player_id, opponent_id, player_role)`: assembles complete 29-column feature dict by calling all subsystem modules:
  - Glicko-2: `_get_player_elo` for all 4 surfaces
  - H2H: `get_h2h` called twice (overall + surface-specific)
  - Form: `compute_rolling_form` (10 and 20 match windows + service stats)
  - Ranking: `get_ranking_features` (ranking + delta)
  - Fatigue: `get_fatigue_features` (days since last, sets in 7 days)
  - Context: tourney_level raw string, surface
  - Sentiment: `_get_sentiment` wrapper — returns None on any error or missing articles

- `build_all_features(conn)`: processes all matches via `matches JOIN tournaments`, builds 2 rows per match (winner + loser), inserts via `INSERT OR REPLACE`. Returns `{"matches_processed": N, "feature_rows_written": N}`.

### Refresh Pipeline (Task 2)

`src/refresh/runner.py` — `refresh_all(db_path, raw_dir, fetch_articles)`:
- Step 1: `ingest_all(db_path, raw_dir)` — download and load new match CSVs
- Step 2: `compute_all_ratings(conn)` — update Glicko-2 ratings
- Step 3 (optional): `fetch_all_articles()` + `score_text()` + `store_sentiment_score()` — fetch and score articles
- Step 4: `build_all_features(conn)` — rebuild full feature matrix
- Each step wrapped in `try/except` — failures logged and captured in return dict, pipeline continues
- Returns `{"steps": {...}, "success": bool}`

`src/refresh/scheduler.py` — `build_scheduler(db_path, hour, minute)`:
- Creates `BackgroundScheduler` with `CronTrigger(hour=hour, minute=minute)`
- Adds `daily_refresh` job pointing to `refresh_all`
- Returns NOT-started scheduler (caller starts in FastAPI lifespan or standalone)

`src/refresh/__main__.py`: CLI entry point for one-shot refresh or scheduled mode.

### Integration Tests (Task 3)

Full suite: **200 tests, 0 failures** (90 Phase 1 + 110 Phase 2):
- 16 builder tests (all keys, ELO population, H2H, ranking, sentiment graceful None, idempotency, look-ahead bias)
- 16 refresh tests (step ordering, fault tolerance, scheduler configuration, lifecycle)
- 29 Glicko-2 tests (unchanged from 02-01)
- 27 feature module tests (unchanged from 02-02)
- 22 sentiment tests (unchanged from 02-03)
- 90 Phase 1 tests (zero regressions)

## Test Results

```
pytest tests/ -x -q --tb=short
200 passed in 1.89s
```

End-to-end look-ahead bias test (`TestLookAheadBias::test_future_match_does_not_change_features_for_earlier_match`) verifies that adding a match on 2024-04-01 does not alter features computed for a match on 2024-01-15 — strict temporal filtering holds end-to-end.

## Commits

| Task | Type | Hash | Description |
|------|------|------|-------------|
| 1 RED | test | 252764e | Failing tests for feature builder and look-ahead bias |
| 1 GREEN | feat | 2cb68d7 | Feature builder implementation |
| 2 RED | test | 66667d7 | Failing tests for refresh runner and scheduler |
| 2 GREEN | feat | 6154190 | Refresh runner and APScheduler scheduler |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test helper inserted match with mismatched tourney_id**
- **Found during:** Task 1 TDD GREEN (test_correct_tourney_and_match_ids)
- **Issue:** `_insert_match(db_conn, tourney_id="T002")` failed FOREIGN KEY constraint because only tournament "T001" was inserted
- **Fix:** Updated test to call `_insert_tournament(db_conn, tourney_id="T002")` before the match insert
- **Files modified:** tests/test_builder.py
- **Verification:** 16/16 builder tests pass

None beyond the above minor test fix. Plan executed essentially as written.

## Self-Check

### Files Created
- src/features/builder.py — FOUND
- src/refresh/__init__.py — FOUND
- src/refresh/runner.py — FOUND
- src/refresh/scheduler.py — FOUND
- src/refresh/__main__.py — FOUND
- tests/test_builder.py — FOUND
- tests/test_refresh.py — FOUND

### Commits
- 252764e — FOUND (test: failing tests for feature builder)
- 2cb68d7 — FOUND (feat: feature builder)
- 66667d7 — FOUND (test: failing tests for refresh)
- 6154190 — FOUND (feat: refresh runner + scheduler)

## Self-Check: PASSED
