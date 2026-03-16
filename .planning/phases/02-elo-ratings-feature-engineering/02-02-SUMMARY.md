---
phase: 02-elo-ratings-feature-engineering
plan: "02"
subsystem: features
tags: [sqlite, pandas, feature-engineering, temporal-safety, look-ahead-bias]

# Dependency graph
requires:
  - phase: 01-data-ingestion-storage
    provides: matches, match_stats, rankings, tournaments tables in SQLite schema
provides:
  - src/features/h2h.py: get_h2h() — head-to-head record with strict temporal filtering and surface filter
  - src/features/ranking.py: get_ranking_features() — latest pre-match ranking and delta
  - src/features/fatigue.py: get_fatigue_features() — days since last match and sets in 7-day window
  - src/features/tourney.py: encode_tourney_level() — ordinal encoding of ATP tournament level
  - src/features/form.py: compute_rolling_form() — rolling win rate and service stats over configurable windows
affects:
  - 02-03-PLAN (feature matrix assembly — these modules are the building blocks)
  - 02-04-PLAN (ELO computation may use h2h and ranking features)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Strict less-than date filtering (tourney_date < :before_date) on all feature queries to prevent look-ahead bias"
    - "Ranking uses <= (ranking_date <= before_date) since ATP weekly rankings are published before matches are played"
    - "UNION ALL pattern for aggregating service stats across winner/loser roles"
    - "7-day window: [match_date - 7 days, match_date) — lower bound inclusive, upper bound exclusive"

key-files:
  created:
    - src/features/__init__.py
    - src/features/h2h.py
    - src/features/ranking.py
    - src/features/fatigue.py
    - src/features/tourney.py
    - src/features/form.py
    - tests/test_features.py
  modified: []

key-decisions:
  - "Ranking uses ranking_date <= before_date (not strict less-than) — ATP weekly rankings published before match day"
  - "H2H surface filter uses JOIN tournaments USING (tourney_id, tour) — no denormalization needed"
  - "Sets counted by parsing score string: hyphenated tokens (e.g. '6-3') each count as one set; RET/W/O/DEF tokens are ignored"
  - "compute_rolling_form accepts windows=[N, M] list to return multiple window sizes in one call"
  - "Service stats aggregate totals across window (sum ace / sum svpt) rather than averaging per-match rates — avoids small-sample distortion"

patterns-established:
  - "All feature functions take (conn, ..., before_date) and enforce strict temporal cutoff"
  - "Feature functions return dict with None for missing data (never raise on empty result)"
  - "TDD: failing test committed first, then implementation committed separately"

requirements-completed: [FEAT-01, FEAT-02, FEAT-03, FEAT-04, FEAT-06]

# Metrics
duration: 4min
completed: 2026-03-16
---

# Phase 2 Plan 02: Feature Modules Summary

**Five temporally-safe feature modules (H2H, rolling form, ranking delta, fatigue, tournament level) with 27 tests proving no look-ahead bias**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-16T18:32:10Z
- **Completed:** 2026-03-16T18:36:22Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Built five independent feature computation modules covering FEAT-01 through FEAT-04 and FEAT-06
- All temporal queries enforce strict less-than date filtering — no look-ahead bias possible
- Two explicit look-ahead bias unit tests prove features for match M are unaffected by adding a future match
- Rolling form supports configurable window sizes via `windows=[10, 20]` parameter
- Fatigue computes both days-since-last and sets-in-7-days with correct boundary conditions (exactly 7 days included, 8 days excluded)

## Task Commits

Each task was committed atomically (TDD pattern):

1. **Task 1+2: Failing tests for all feature modules** - `3e1fee0` (test)
2. **Task 1+2: Implement all five feature modules** - `d296207` (feat)

**Plan metadata:** (docs commit follows)

_Note: Tasks 1 and 2 share the same test file; tests for form.py were included in the initial RED commit._

## Files Created/Modified
- `src/features/__init__.py` — Package init for features module
- `src/features/h2h.py` — `get_h2h()`: H2H record with strict date filter, optional surface filter via JOIN tournaments
- `src/features/ranking.py` — `get_ranking_features()`: most recent pre-match ranking + delta (previous - current, positive = improved)
- `src/features/fatigue.py` — `get_fatigue_features()`: days since last match, sets in 7-day window with score parsing
- `src/features/tourney.py` — `encode_tourney_level()`: ordinal encoding G=4, M=3, A=2, F=2, D=1, C=1, unknown=0
- `src/features/form.py` — `compute_rolling_form()`: rolling win rate per configurable window + aggregated service stats
- `tests/test_features.py` — 27 tests covering all modules, temporal boundary conditions, look-ahead bias

## Decisions Made
- **Ranking uses `ranking_date <= before_date`** (not strict less-than): ATP weekly rankings are published on Mondays before the week's matches. Using `<=` is correct real-world behavior. Strict less-than would incorrectly exclude the ranking published on the match date.
- **Service stats use aggregated totals** (`sum(ace)/sum(svpt)` across all window matches) rather than per-match averages. This avoids small-sample distortion from short matches where a single stat dominates the average.
- **`compute_rolling_form` accepts `windows` list**: returning multiple window sizes in one database round-trip is more efficient than multiple calls. Returns keys `form_win_rate_10`, `form_win_rate_20`, etc. dynamically.
- **Score parsing in fatigue**: counts hyphenated set tokens (e.g., `6-3`) to determine sets played; ignores `RET`, `W/O`, `DEF` tokens. Tiebreak annotations like `(7)` are stripped before parsing.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

**Pre-existing out-of-scope issue:** `src/db/schema.sql` has uncommitted modifications (from another plan outside scope) that add 3 new tables (`match_features`, `articles`, `article_sentiment`). This caused `test_loader.py::test_schema_creates_all_tables` to fail. The failure is unrelated to this plan's changes — it was caused by a schema divergence already present in the working tree. Documented in `deferred-items.md`.

All 27 feature tests pass. All 75 Phase 1 tests pass.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All five feature modules are ready for use in feature matrix assembly (02-03)
- `get_h2h`, `compute_rolling_form`, `get_ranking_features`, `get_fatigue_features`, `encode_tourney_level` are importable from `src.features.*`
- No blockers — all temporal safety proofs are in place via look-ahead bias unit tests

---
*Phase: 02-elo-ratings-feature-engineering*
*Completed: 2026-03-16*
