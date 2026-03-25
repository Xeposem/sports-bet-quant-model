---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Ready to execute
stopped_at: Completed 14-03-PLAN.md
last_updated: "2026-03-25T23:13:35.349Z"
progress:
  total_phases: 15
  completed_phases: 13
  total_plans: 44
  completed_plans: 43
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-15)

**Core value:** Accurate, data-driven predictions that identify positive expected value betting opportunities in tennis — measured by demonstrable edge over bookmaker lines in backtesting
**Current focus:** Phase 14 — add-court-speed-index-per-tournament

## Current Position

Phase: 14 (add-court-speed-index-per-tournament) — EXECUTING
Plan: 3 of 3

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
| Phase 05-fastapi-backend P03 | 25 | 2 tasks | 6 files |
| Phase 06-react-dashboard-core P01 | 11 | 2 tasks | 33 files |
| Phase 06-react-dashboard-core P03 | 7 | 2 tasks | 8 files |
| Phase 06-react-dashboard-core P02 | 8 | 2 tasks | 16 files |
| Phase 06-react-dashboard-core P04 | 8 | 2 tasks | 9 files |
| Phase 06-react-dashboard-core P05 | 20 | 2 tasks | 8 files |
| Phase 06-react-dashboard-core P06 | 5 | 1 tasks | 2 files |
| Phase 07-advanced-models-ensemble P01 | 4 | 2 tasks | 7 files |
| Phase 07-advanced-models-ensemble P02 | 4 | 2 tasks | 4 files |
| Phase 07-advanced-models-ensemble P03 | 8 | 2 tasks | 4 files |
| Phase 07-advanced-models-ensemble PP04 | 4 | 2 tasks | 5 files |
| Phase 08-player-props P01 | 572 | 3 tasks | 10 files |
| Phase 08-player-props P02 | 6 | 2 tasks | 5 files |
| Phase 09-simulation-signals-paper-trading P01 | 34 | 3 tasks | 13 files |
| Phase 09-simulation-signals-paper-trading P04 | 4 | 2 tasks | 6 files |
| Phase 09-simulation-signals-paper-trading P02 | 15 | 3 tasks | 7 files |
| Phase 09-simulation-signals-paper-trading P03 | 448 | 3 tasks | 10 files |
| Phase 10-prizepicks-screenshot-cv-tool-for-automatic-atp-prop-extraction P01 | 575 | 2 tasks | 5 files |
| Phase 10-prizepicks-screenshot-cv-tool-for-automatic-atp-prop-extraction P02 | 7 | 2 tasks | 6 files |
| Phase 10-prizepicks-screenshot-cv-tool-for-automatic-atp-prop-extraction P02 | 7 | 3 tasks | 6 files |
| Phase 11-update-data-ingestion-to-use-stats-tennismylife-org-for-most-recent-atp-match-data P01 | 25 | 2 tasks | 4 files |
| Phase 11-update-data-ingestion-to-use-stats-tennismylife-org-for-most-recent-atp-match-data P02 | 4 | 2 tasks | 4 files |
| Phase 12 P01 | 8 | 1 tasks | 3 files |
| Phase 12-add-pinnacle-odds-as-a-feature-and-retrain-on-the-residual P02 | 15 | 2 tasks | 8 files |
| Phase 12-add-pinnacle-odds-as-a-feature-and-retrain-on-the-residual P03 | 7 | 1 tasks | 4 files |
| Phase 13-implement-ev-threshold-filtering-only-bet-when-divergence-exceeds-x-percent P01 | 35 | 2 tasks | 8 files |
| Phase 13-implement-ev-threshold-filtering-only-bet-when-divergence-exceeds-x-percent P02 | 18 | 2 tasks | 9 files |
| Phase 14-add-court-speed-index-per-tournament P01 | 277 | 2 tasks | 5 files |
| Phase 14-add-court-speed-index-per-tournament P03 | 3 | 2 tasks | 6 files |

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
- [Phase 05-fastapi-backend]: Module-level imports in router files required for unittest.mock.patch at module scope — lazy imports inside closures cannot be patched
- [Phase 05-fastapi-backend]: async_app test fixture uses tmp_path file DB not :memory: — sync sqlite3.connect(':memory:') opens new empty DB each call, cannot share schema with async engine
- [Phase 06-react-dashboard-core]: Vitest 4.x requires importing defineConfig from vitest/config for test block TypeScript recognition
- [Phase 06-react-dashboard-core]: shadcn/ui CLI not automatable for React 19 peer deps — all 9 UI component files created manually
- [Phase 06-react-dashboard-core]: getByRole(heading) preferred over getByText in tests where text appears in multiple roles (tab + heading)
- [Phase 06-react-dashboard-core]: Radix Select disallows value='' — used __all__ sentinel string for All option in FilterBar
- [Phase 06-react-dashboard-core]: CalibrationChart layers type fixed with 'as any' — Nivo ScatterPlotCustomSvgLayer incompatible with direct function reference
- [Phase 06-react-dashboard-core]: Lightweight Charts v5 addSeries(BaselineSeries) API used, not deprecated addBaselineSeries()
- [Phase 06-react-dashboard-core]: Hook test mocks use as unknown as ReturnType<...> for TanStack Query v5 type compatibility
- [Phase 06-react-dashboard-core]: CalibrationChart empty state heading/body use distinct text to avoid getByText multiple-element test failures
- [Phase 06-react-dashboard-core]: Test mocks use 'as unknown as ReturnType' for TanStack Query UseQueryResult type compatibility
- [Phase 06-react-dashboard-core]: useRefreshAll polls /refresh/{job_id} every 2 seconds via setInterval until status=complete or error
- [Phase 06-react-dashboard-core]: ErrorBoundary wraps TabNav only (not Header) so header controls remain usable during render error recovery
- [Phase 06-react-dashboard-core]: Brier score reads models.data?.data?.[0]?.brier_score — first entry in models array is current active model
- [Phase 07-advanced-models-ensemble]: base.py holds shared utilities; logistic.py holds model-specific logic for clean separation enabling future model types
- [Phase 07-advanced-models-ensemble]: trainer.py becomes a re-export shim so walk_forward.py, api/main.py, odds/cli.py require zero import changes
- [Phase 07-advanced-models-ensemble]: store_prediction merges p5/p50/p95 defaults before SQL INSERT for backward compatibility with legacy caller dicts
- [Phase 07-advanced-models-ensemble]: XGB_FEATURES has 28 entries: 12 logistic + 11 new numeric + 5 one-hot context (surface_clay/grass/hard + level_G/M) — plan comment said 27 but actual list totals 28
- [Phase 07-advanced-models-ensemble]: XGBoost uses ALL match_features columns (28 pairwise differentials) per user decision — no manual feature selection, let trees decide
- [Phase 07-advanced-models-ensemble]: build_xgb_training_matrix train_end parameter allows same function for both registry train() and walk-forward fold — avoids SQL duplication; Plan 04 dispatches to it when model_version==xgboost_v1
- [Phase 07-advanced-models-ensemble]: XGBClassifier uses eval_metric=logloss and verbosity=0 — use_label_encoder removed in XGBoost 1.6
- [Phase 07-advanced-models-ensemble]: pm imported at module level via try/except in bayesian.py to allow @patch(src.model.bayesian.pm) in tests while preserving graceful degradation
- [Phase 07-advanced-models-ensemble]: scipy downgraded to <1.13 to fix arviz 0.17.1 incompatibility (scipy.signal.gaussian removed in scipy 1.13)
- [Phase 07-advanced-models-ensemble]: Lazy __init__.py wrappers for bayesian_v1 prevent PyMC/PyTensor load at MODEL_REGISTRY import time
- [Phase 07-advanced-models-ensemble]: ensemble_v1 registered in MODEL_REGISTRY; XGB test prediction uses build_fold_xgb_test_matches (28-col); _train_model_for_fold dispatches to correct feature path per model_version
- [Phase 08-player-props]: statsmodels GLM NegBin: scale attribute holds alpha dispersion parameter for compute_pmf
- [Phase 08-player-props]: max_k = max(50, int(mu * 6)) for NegBin tail coverage -- mu*4 insufficient for high mu low alpha
- [Phase 08-player-props]: match_stats uses player_role not player_id -- training queries join through matches to get winner_id/loser_id
- [Phase 08-player-props]: predict_and_store imports PROP_REGISTRY at function level to avoid circular import with src.props.__init__
- [Phase 08-player-props]: GET /accuracy registered before GET '' route -- FastAPI would treat 'accuracy' as path param otherwise
- [Phase 08-player-props]: resolve_props joins match_stats through matches using player_role -- match_stats has no player_id column
- [Phase 08-player-props]: p_hit = p_over if direction=over else 1-p_over for consistent prop line evaluation in both directions
- [Phase 08-player-props]: useSubmitPropLine handles POST response as PropLineResponse (id only), then refetches GET /props to find matching PropPrediction by id
- [Phase 08-player-props]: PropLineResponse type added separately from PropPrediction -- POST returns minimal record, GET returns full prediction with pmf/p_hit
- [Phase 08-player-props]: PmfChart slices pmf array to mu +/- 15 range to avoid rendering 50+ empty bars at chart edges
- [Phase 09-simulation-signals-paper-trading]: simulation_results single-row overwrite pattern (DELETE + INSERT) — last run always accessible via GET /simulation/result
- [Phase 09-simulation-signals-paper-trading]: signals INSERT OR IGNORE upsert from predictions on each GET /signals — idempotent, no duplicate signals
- [Phase 09-simulation-signals-paper-trading]: kelly_stake in signals list uses $1,000 reference bankroll — context-independent sizing for display
- [Phase 09-simulation-signals-paper-trading]: CORS allow_methods extended to PATCH and DELETE for paper trading and CRUD delete endpoints
- [Phase 09-simulation-signals-paper-trading]: @radix-ui/react-dialog installed manually (not via shadcn/ui CLI) — React 19 peer deps conflict; followed Phase 6 manual component creation pattern
- [Phase 09-simulation-signals-paper-trading]: FAB approach chosen for ManualEntryModal trigger — accessible from any tab without modifying Header.tsx logic
- [Phase 09-simulation-signals-paper-trading]: Synthetic UTCTimestamp: step * 86400 + baseTimestamp satisfies Lightweight Charts strictly-increasing time requirement for step-based Monte Carlo paths
- [Phase 09-simulation-signals-paper-trading]: useRunSimulation.data takes precedence over useSimulationResult.data so fresh mutation results display immediately without cache round-trip
- [Phase 09-simulation-signals-paper-trading]: PaperEquityChart uses LineSeries not BaselineSeries — no reference baseline for paper equity, green/red color by total_pnl sign
- [Phase 09-simulation-signals-paper-trading]: SignalsTab EV threshold stored in localStorage under key ev_threshold — persists slider position across page reloads
- [Phase 10-prizepicks-screenshot-cv-tool-for-automatic-atp-prop-extraction]: TesseractNotFoundError returns status=tesseract_not_found dict inside scan_image_bytes, converted to HTTP 503 at endpoint level
- [Phase 10-prizepicks-screenshot-cv-tool-for-automatic-atp-prop-extraction]: POST /scan registered before POST '' in props.py router to avoid FastAPI routing conflict
- [Phase 10-prizepicks-screenshot-cv-tool-for-automatic-atp-prop-extraction]: useScanPropScreenshot does NOT set Content-Type header — browser sets multipart boundary automatically for FormData
- [Phase 10-prizepicks-screenshot-cv-tool-for-automatic-atp-prop-extraction]: PropScanPreview expands card.directions into individual ScanRow entries (one per direction) for independent deselect
- [Phase 10-prizepicks-screenshot-cv-tool-for-automatic-atp-prop-extraction]: useScanPropScreenshot does NOT set Content-Type header — browser must set multipart boundary automatically for FormData
- [Phase 10-prizepicks-screenshot-cv-tool-for-automatic-atp-prop-extraction]: PropScanPreview expands card.directions into individual ScanRow entries (one per direction) for independent deselect
- [Phase 11-update-data-ingestion-to-use-stats-tennismylife-org-for-most-recent-atp-match-data]: Synthetic TML player IDs start at 900000 — above Sackmann max (~230000) to guarantee no collision
- [Phase 11-update-data-ingestion-to-use-stats-tennismylife-org-for-most-recent-atp-match-data]: tml_downloader output filename prefixed tml_YYYY.csv — avoids collision with Sackmann atp_matches_YYYY.csv in same raw_dir
- [Phase 11-update-data-ingestion-to-use-stats-tennismylife-org-for-most-recent-atp-match-data]: ingest_year_tml reads winner_id/loser_id as str dtype then casts to Int64 after normalise_tml_dataframe — avoids ValueError on alphanumeric TML IDs
- [Phase 11-update-data-ingestion-to-use-stats-tennismylife-org-for-most-recent-atp-match-data]: auto mode catches requests.exceptions.HTTPError (not generic Exception) for precise Sackmann 404 detection without masking TML errors
- [Phase 12]: _get_pinnacle_prob uses function-level import of power_method_devig to match existing lazy import pattern
- [Phase 12]: Graceful fallback (None, None, 1) for both missing odds and invalid odds — consistent with has_no_elo pattern
- [Phase 12-add-pinnacle-odds-as-a-feature-and-retrain-on-the-residual]: XGB_FEATURES expanded to 32 (not 31 as planned) — original list had 30 entries; 30+2=32 is correct count
- [Phase 12-add-pinnacle-odds-as-a-feature-and-retrain-on-the-residual]: predictor.py _FEATURE_QUERY extended with pinnacle columns — auto-fix to prevent IndexError when model uses 16-col LOGISTIC_FEATURES
- [Phase 12-add-pinnacle-odds-as-a-feature-and-retrain-on-the-residual]: predict_pinnacle delegates to predict() — ensemble blending is model-agnostic; no duplication needed
- [Phase 12-add-pinnacle-odds-as-a-feature-and-retrain-on-the-residual]: Patch target for train_pinnacle mock tests is src.model.MODEL_REGISTRY — train_pinnacle uses local import pattern matching existing ensemble.train()
- [Phase 13-implement-ev-threshold-filtering-only-bet-when-divergence-exceeds-x-percent]: CLV gate at compute_kelly_bet level uses clv_threshold=0.0 default for backward compat; CLI and API default to 0.03 per D-04
- [Phase 13-implement-ev-threshold-filtering-only-bet-when-divergence-exceeds-x-percent]: Loser-side pinnacle_prob = 1.0 - pinnacle_prob_market (devigged probs sum to 1.0); has_no_pinnacle derived from pinnacle_prob_market is None
- [Phase 13-implement-ev-threshold-filtering-only-bet-when-divergence-exceeds-x-percent]: run_clv_sweep docstring explains DB side-effects; after sweep, caller runs regular backtest at configured threshold to leave DB consistent
- [Phase 13-implement-ev-threshold-filtering-only-bet-when-divergence-exceeds-x-percent]: CLV sliders do not apply client-side filtering on Signals/Paper tabs — signals lack pinnacle_prob; values stored for future API use
- [Phase 13-implement-ev-threshold-filtering-only-bet-when-divergence-exceeds-x-percent]: @nivo/line installed for sweep chart — was absent from package.json despite other nivo packages being present
- [Phase 14-add-court-speed-index-per-tournament]: COUNT(DISTINCT match_num) for min_matches threshold to avoid double-counting winner/loser stat rows
- [Phase 14-add-court-speed-index-per-tournament]: Percentile-rank normalization for CSI values — bounded [0,1], robust to outliers
- [Phase 14-add-court-speed-index-per-tournament]: numpy.percentile used in API routers for tercile computation — SQLite lacks PERCENTILE_CONT

### Roadmap Evolution

- Phase 10 added: PrizePicks screenshot CV tool for automatic ATP prop extraction
- Phase 11 added: Update data ingestion to use stats.tennismylife.org for most recent ATP match data
- Phase 12 added: Add Pinnacle odds as a feature and retrain on the residual
- Phase 13 added: Implement EV threshold filtering — only bet when divergence exceeds X percent
- Phase 14 added: Add court speed index per tournament
- Phase 15 added: Explore prop markets — NegBin models may have more edge on aces and games than the moneyline model

### Pending Todos

None yet.

### Blockers/Concerns

- [Research]: Sackmann CSV schema changes across years (pre/post 2011 column availability) — needs validation during Phase 1 planning
- [Research]: Historical bookmaker odds source for EV backtesting not yet identified — gap must be resolved before Phase 3
- [Research]: PyMC hierarchical model for tennis prop stat distributions is niche — Phase 8 planning should include a research step
- [Research]: Glicko-2 vs standard Elo decision deferred to Phase 2 planning

## Session Continuity

Last session: 2026-03-25T23:13:35.342Z
Stopped at: Completed 14-03-PLAN.md
Resume file: None
