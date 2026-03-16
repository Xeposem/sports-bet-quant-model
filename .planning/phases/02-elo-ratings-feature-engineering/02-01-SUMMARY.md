---
phase: 02-elo-ratings-feature-engineering
plan: "01"
subsystem: ratings
tags: [glicko2, ratings, schema, tdd, feature-engineering]
dependency_graph:
  requires: [src/db/schema.sql, src/db/connection.py, tests/conftest.py]
  provides: [src/ratings/glicko.py, src/ratings/seeder.py, src/ratings/decay.py]
  affects: [player_elo table, match_features table, articles table, article_sentiment table]
tech_stack:
  added: [glicko2==2.1.0]
  patterns: [weekly-batch-glicko2, surface-specific-tracks, frozen-opponent-ratings, tdd-red-green]
key_files:
  created:
    - src/ratings/__init__.py
    - src/ratings/seeder.py
    - src/ratings/decay.py
    - src/ratings/glicko.py
    - tests/test_glicko.py
  modified:
    - src/db/schema.sql
    - requirements.txt
    - pyproject.toml
    - tests/test_loader.py
decisions:
  - "Piecewise logarithmic seeder: two segments (rank 1-100 and 100-300) with rank 100 as anchor at 1500 for accurate three-point calibration"
  - "Tournament weighting via fractional outcome: effective_outcome = base * tw + 0.5 * (1-tw) rather than K-factor scaling (not natively supported by glicko2 library)"
  - "Retirement weighting applied on top of tourney weighting: half the deviation from 0.5 for retirement outcomes"
  - "Glicko-2 Player.rating attribute directly modified for decay (library does not expose a setter; internal attribute access is consistent with library version 2.1.0)"
  - "test_sentiment pre-existing failure excluded from verification: TypeError from list|None union syntax requires Python 3.10+; unrelated to 02-01 scope"
metrics:
  duration_seconds: 472
  completed_date: "2026-03-16"
  tasks_completed: 2
  files_created: 5
  files_modified: 4
---

# Phase 2 Plan 1: Glicko-2 Rating Engine and Schema Migration Summary

**One-liner:** Surface-specific Glicko-2 ratings with weekly batch processing, rank-based seeding, inactivity decay, and full history persistence using frozen opponent ratings to prevent look-ahead bias.

## What Was Built

### Schema Migration (Task 1)
- Extended `player_elo` table with `rd REAL DEFAULT 350.0`, `volatility REAL DEFAULT 0.06`, `last_played_date TEXT` columns
- Created `match_features` table (wide format, one row per player per match) with 28 columns covering Glicko-2 ratings, H2H, form, service stats, ranking, fatigue, and sentiment features
- Created `articles` table for press conference transcripts and news articles
- Created `article_sentiment` table for scored sentiment output
- Added indexes: `idx_articles_player`, `idx_match_features_pk`

### Seeder Module (Task 1)
`src/ratings/seeder.py` — `seed_rating_from_rank(rank)`:
- Piecewise logarithmic curve with rank 100 as anchor at 1500
- Segment 1 (rank 1-100): log(rank)/log(100) interpolation from 1800 to 1500
- Segment 2 (rank 100-300): log(rank/100)/log(3) interpolation from 1500 to 1350
- Returns 1500.0 for None or rank <= 0

### Decay Module (Task 1)
`src/ratings/decay.py` — `apply_decay_if_needed(player_rating, surface, days_inactive)`:
- `SURFACE_THRESHOLDS = {"Hard": 90, "Clay": 180, "Grass": 330}` (days)
- Multiplicative decay: `gap * (1 - 0.025)^months_over_threshold`
- Returns unchanged rating if below threshold

### Glicko-2 Engine (Task 2)
`src/ratings/glicko.py` — `compute_all_ratings(conn)`:
- Loads all matches joined with tournaments for surface/tourney_level
- Orders by tourney_date, round (CASE mapping), match_num for canonical order
- Groups by ISO week using `date.isocalendar()`
- Freezes opponent ratings at week-start before processing matches
- Four surface tracks (Hard, Clay, Grass, Overall) updated independently
- `_effective_outcome`: tournament weighting + retirement halving
- `did_not_compete()` called for known players missing from each week
- Inactivity decay applied via `apply_decay_if_needed` after each week
- Snapshot written to `player_elo` via INSERT OR REPLACE per (player_id, surface, week)
- Returns `{total_weeks, total_players, total_snapshots}` summary

## Test Results

29 tests in `tests/test_glicko.py` — all pass:
- 6 schema migration tests (ELO-01)
- 6 seeder tests (ELO-02)
- 7 decay tests (ELO-03)
- 10 engine tests (frozen ratings, surface independence, RD growth, retirement weight, Grand Slam vs ATP 250, seeding, look-ahead safety)

Full suite (excluding pre-existing test_sentiment failures): 146 passed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Rank-100 seeder calibration**
- **Found during:** Task 1 TDD GREEN
- **Issue:** Single-segment log(rank)/log(300) formula placed rank 100 at ~1437, not ~1500
- **Fix:** Replaced with piecewise logarithmic formula using rank 100 as explicit anchor
- **Files modified:** `src/ratings/seeder.py`

**2. [Rule 1 - Bug] test_loader.py hardcoded table counts**
- **Found during:** Task 1 full suite regression check
- **Issue:** Two tests asserted exactly 7 tables; schema migration added 3 tables (match_features, articles, article_sentiment)
- **Fix:** Updated assertions to expect 10 tables with explanatory comment
- **Files modified:** `tests/test_loader.py`

## Self-Check

### Files Created
- `src/ratings/__init__.py` — exists
- `src/ratings/seeder.py` — exists, exports seed_rating_from_rank
- `src/ratings/decay.py` — exists, exports apply_decay_if_needed, SURFACE_THRESHOLDS
- `src/ratings/glicko.py` — exists, exports compute_all_ratings, 521 lines
- `tests/test_glicko.py` — exists, 538 lines, 29 tests

### Schema Artifacts
- `player_elo` has rd, volatility, last_played_date columns — verified via PRAGMA test
- `match_features` table exists — verified via PRAGMA test
- `articles` and `article_sentiment` tables exist — verified via PRAGMA test

### Commits
- 4fd5c79: feat(02-01): schema migration and Glicko-2 seeder + decay modules
- ce49dd9: feat(02-01): Glicko-2 weekly batch engine with snapshot persistence

## Self-Check: PASSED
