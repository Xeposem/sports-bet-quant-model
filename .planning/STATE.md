---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: planning
stopped_at: Completed 05-fastapi-backend-05-02-PLAN.md
last_updated: "2026-03-18T02:59:49.508Z"
last_activity: 2026-03-15 — Roadmap created, 48 requirements mapped across 9 phases
progress:
  total_phases: 9
  completed_phases: 4
  total_plans: 15
  completed_plans: 14
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-15)

**Core value:** Accurate, data-driven predictions that identify positive expected value betting opportunities in tennis — measured by demonstrable edge over bookmaker lines in backtesting
**Current focus:** Phase 1 — Data Ingestion & Storage

## Current Position

Phase: 1 of 9 (Data Ingestion & Storage)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-03-15 — Roadmap created, 48 requirements mapped across 9 phases

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: none yet
- Trend: -

*Updated after each plan completion*
| Phase 01-data-ingestion-storage P01 | 5 | 2 tasks | 11 files |
| Phase 01-data-ingestion-storage P02 | 8 | 2 tasks | 6 files |
| Phase 01-data-ingestion-storage P03 | 4 | 2 tasks | 4 files |
| Phase 01-data-ingestion-storage P03 | 10 | 3 tasks | 4 files |
| Phase 02-elo-ratings-feature-engineering P02 | 4 | 2 tasks | 7 files |
| Phase 02-elo-ratings-feature-engineering P03 | 4 | 2 tasks | 7 files |
| Phase 02-elo-ratings-feature-engineering P01 | 472 | 2 tasks | 9 files |
| Phase 02-elo-ratings-feature-engineering P04 | 424 | 3 tasks | 9 files |
| Phase 03-baseline-model-ev-framework PP02 | 3 | 2 tasks | 5 files |
| Phase 03-baseline-model-ev-framework P01 | 328 | 2 tasks | 9 files |
| Phase 03-baseline-model-ev-framework P03 | 20 | 2 tasks | 4 files |
| Phase 04-backtesting-engine P01 | 5 | 2 tasks | 6 files |
| Phase 04-backtesting-engine P02 | 25 | 2 tasks | 4 files |
| Phase 05-fastapi-backend P01 | 6 | 2 tasks | 10 files |
| Phase 05-fastapi-backend P02 | 455 | 2 tasks | 7 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-work]: Manual PrizePicks line entry only — TOS prohibits scraping
- [Pre-work]: Free data sources (Sackmann) only — no paid APIs for v1
- [Pre-work]: Python 3.12 required — PyMC v5 does not support Python 3.13
- [Pre-work]: Build order enforced: data → features → baseline → backtest → API → frontend → advanced models → props → paper trading
- [Phase 01-data-ingestion-storage]: Python 3.9 compatible sqlite3.connect() — autocommit kwarg requires 3.12; omitted for backwards compatibility
- [Phase 01-data-ingestion-storage]: WAL journal_mode verified via file-based DB in tests — in-memory SQLite always reports 'memory' mode
- [Phase 01-data-ingestion-storage]: MATCH_DTYPES has 49 keys — plan referenced 44 but RESEARCH.md Pattern 1 defines 49 actual Sackmann columns
- [Phase 01-data-ingestion-storage]: Per-column stat updates for retirement rows avoid FutureWarning in pandas 2.x on dtype-incompatible bulk assignment
- [Phase 01-data-ingestion-storage]: ON CONFLICT DO NOTHING tracked via changes() per-row to enable accurate inserted/skipped counts
- [Phase 01-data-ingestion-storage]: check_duplicates test uses no-PK schema — SQLite PRIMARY KEY always enforced; test validates SQL detection logic only
- [Phase 01-data-ingestion-storage]: overall_valid excludes retirement_ratio.in_range — 3-5% range is a soft warning; hard failures are duplicates, date format, and temporal safety only
- [Phase 01-data-ingestion-storage]: check_duplicates test uses no-PK schema — SQLite PRIMARY KEY always enforced; test validates SQL detection logic only
- [Phase 01-data-ingestion-storage]: overall_valid excludes retirement_ratio.in_range — 3-5% range is a soft warning; hard failures are duplicates, date format, and temporal safety only
- [Phase 01-data-ingestion-storage]: validate-only mode calls init_db before validation to ensure schema exists on fresh databases
- [Phase 02-elo-ratings-feature-engineering]: Ranking uses ranking_date <= before_date (not strict less-than) — ATP weekly rankings published before match day
- [Phase 02-elo-ratings-feature-engineering]: Service stats aggregate totals across window (sum ace / sum svpt) rather than per-match averages — avoids small-sample distortion
- [Phase 02-elo-ratings-feature-engineering]: compute_rolling_form accepts windows list to return multiple window sizes in one DB round-trip
- [Phase 02-elo-ratings-feature-engineering]: Lazy ML pipeline loading: _sentiment_pipe=None at module level, initialized in _get_pipeline() to avoid 268MB DistilBERT download at import time
- [Phase 02-elo-ratings-feature-engineering]: All sentiment tests mock _get_pipeline() return value — zero model downloads, suite runs in under 1s
- [Phase 02-elo-ratings-feature-engineering]: Python 3.9 compatible Optional[List[...]] type hints in fetcher.py — list|None PEP 604 syntax fails on actual runtime Python 3.9
- [Phase 02-elo-ratings-feature-engineering]: Piecewise logarithmic seeder with rank 100 as anchor at 1500 for accurate three-point calibration
- [Phase 02-elo-ratings-feature-engineering]: Tournament weighting via fractional outcome (effective_outcome = base * tw + 0.5 * (1-tw)) since glicko2 library does not support K-factor scaling
- [Phase 02-elo-ratings-feature-engineering]: INSERT OR REPLACE for match_features idempotency — simpler syntax, same semantics as ON CONFLICT DO UPDATE
- [Phase 02-elo-ratings-feature-engineering]: build_scheduler returns NOT-started scheduler — caller controls lifecycle for FastAPI lifespan pattern
- [Phase 02-elo-ratings-feature-engineering]: refresh_all uses module-level imports to allow patching at module scope in tests
- [Phase 03-baseline-model-ev-framework]: CalibratedClassifierCV(FrozenEstimator(pipeline)) used — cv='prefit' deprecated in sklearn 1.6, removed in 1.8
- [Phase 03-baseline-model-ev-framework]: compute_time_weights reference_date defaults to max date in list for reproducible training (not date.today())
- [Phase 03-baseline-model-ev-framework]: NULL Elo imputed as 1500.0 via COALESCE in SQL; has_no_elo_w/has_no_elo_l boolean indicators added for missing Elo detection
- [Phase 03-baseline-model-ev-framework]: token_set_ratio preferred over token_sort_ratio for player name subset matching (100% vs 72.7% for Djokovic in Novak Djokovic)
- [Phase 03-baseline-model-ev-framework]: predict_match returns [winner_pred, loser_pred] — winner has outcome=1 for brier/log-loss, loser has outcome=0
- [Phase 03-baseline-model-ev-framework]: get_db_path() in cli.py is patchable (TENNIS_DB env var) for test isolation without real DB
- [Phase 04-backtesting-engine]: Year-based walk-forward folds with train_end=Jan 1 of test year for interpretable annual performance analysis
- [Phase 04-backtesting-engine]: Both winner and loser sides processed per match — model bets on whichever side has positive EV, all decisions logged
- [Phase 04-backtesting-engine]: kelly_bet > 0 filter for ROI: only bets placed count toward denominator — zero-stake decisions excluded
- [Phase 04-backtesting-engine]: matplotlib.use('Agg') at module level — must be before pyplot import for headless environments
- [Phase 04-backtesting-engine]: Rank tier uses bet-on player rank: outcome=1 => winner_rank, outcome=0 => loser_rank
- [Phase 05-fastapi-backend]: StarletteHTTPException handler required (not FastAPI HTTPException) to catch routing 404s in FastAPI 0.128+
- [Phase 05-fastapi-backend]: greenlet==3.0.3 pinned for Python 3.9 + Windows compatibility
- [Phase 05-fastapi-backend]: async_app fixture sets app.state directly, bypassing lifespan, for isolated endpoint tests
- [Phase 05-fastapi-backend]: PRAGMA foreign_keys=OFF required per-connection in aiosqlite test seeder for leaf table inserts without parent rows
- [Phase 05-fastapi-backend]: props.py GET stub reused from Plan 01 scaffolding — no recreation needed

### Pending Todos

None yet.

### Blockers/Concerns

- [Research]: Sackmann CSV schema changes across years (pre/post 2011 column availability) — needs validation during Phase 1 planning
- [Research]: Historical bookmaker odds source for EV backtesting not yet identified — gap must be resolved before Phase 3
- [Research]: PyMC hierarchical model for tennis prop stat distributions is niche — Phase 8 planning should include a research step
- [Research]: Glicko-2 vs standard Elo decision deferred to Phase 2 planning

## Session Continuity

Last session: 2026-03-18T02:59:49.504Z
Stopped at: Completed 05-fastapi-backend-05-02-PLAN.md
Resume file: None
