# Roadmap: Sports Betting Quant Model

## Overview

This project builds a quantitative ATP tennis prediction platform from the data layer up to a live-signal React dashboard. The build order enforces hard dependencies: clean data before any model training, a validated baseline model before adding complexity, a backtesting engine before the API, and the API before the frontend. The most dangerous failure mode — building a polished dashboard on an unvalidated model — is explicitly blocked by requiring backtest evidence of edge before any frontend work begins. The result is a system that produces calibrated match outcome probabilities, calculates expected value against bookmaker odds, and tracks paper trading performance across multiple model approaches.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Data Ingestion & Storage** - Ingest and clean Sackmann ATP data into SQLite with temporal integrity enforced (completed 2026-03-16)
- [ ] **Phase 2: Elo Ratings & Feature Engineering** - Compute surface-specific Elo ratings and all predictive features
- [x] **Phase 3: Baseline Model & EV Framework** - Train logistic regression baseline and calculate expected value against bookmaker odds (completed 2026-03-17)
- [ ] **Phase 4: Backtesting Engine** - Walk-forward backtest with Kelly bet sizing validates historical edge before any UI work
- [ ] **Phase 5: FastAPI Backend** - REST API serves validated model predictions and analytics to the frontend
- [x] **Phase 6: React Dashboard Core** - Dashboard visualizes all backtest metrics, calibration, and EV signals (completed 2026-03-18)
- [x] **Phase 7: Advanced Models & Ensemble** - GBM and Bayesian models added; multi-model ensemble replaces single baseline (completed 2026-03-18)
- [ ] **Phase 8: Player Props** - Poisson/NegBin prop prediction models, manual PrizePicks line entry, PMF visualization, and accuracy tracking
- [ ] **Phase 9: Simulation, Signals & Paper Trading** - Monte Carlo simulation, automated signal generation, and live paper trading

## Phase Details

### Phase 1: Data Ingestion & Storage
**Goal**: Clean, temporally-safe ATP match data exists in SQLite and is ready for feature engineering
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05
**Success Criteria** (what must be TRUE):
  1. Running the ingestion script downloads and processes all available Sackmann CSV files into a SQLite database without errors
  2. Querying the database returns no duplicate match records across years
  3. Matches with "RET", "W/O", or "DEF" scores are filtered or flagged and the filtered row count is between 3-5% of total matches
  4. Any feature computed from the dataset uses only information available before the match date -- no future data is accessible to the model
  5. The SQLite schema has a `tour` column or equivalent that supports future WTA extension without migration
**Plans:** 3/3 plans complete
Plans:
- [x] 01-01-PLAN.md -- Project scaffolding, SQLite schema, DB connection factory, test infrastructure
- [x] 01-02-PLAN.md -- Download, clean, classify, and load ATP match data into SQLite
- [x] 01-03-PLAN.md -- Data validation, quality reporting, CLI entry point, integration tests

### Phase 2: Elo Ratings & Feature Engineering
**Goal**: Every match in the dataset has a complete feature row including surface-specific Glicko-2 ratings, rolling form, H2H, fatigue, sentiment, and ranking features computed without look-ahead bias
**Depends on**: Phase 1
**Requirements**: ELO-01, ELO-02, ELO-03, FEAT-01, FEAT-02, FEAT-03, FEAT-04, FEAT-05, FEAT-06, FEAT-07, FEAT-08
**Success Criteria** (what must be TRUE):
  1. Each match row has three distinct Elo columns (hard, clay, grass) reflecting only matches played before that match date
  2. Players with no matches for 6+ months show lower Elo confidence weight or rating decay -- the rating is not frozen at last-played value
  3. Feature matrix includes H2H record, rolling win rate, service stats, days since last match, sets played in last 7 days, ranking, ranking delta, and tournament level for both players
  4. User can trigger article fetching for sentiment analysis from the dashboard and see updated sentiment scores for targeted players
  5. Removing any single match from the dataset does not change feature values for matches played before it -- look-ahead bias unit test passes
**Plans:** 3/4 plans executed
Plans:
- [ ] 02-01-PLAN.md -- Schema migration + Glicko-2 rating engine with surface-specific tracks, seeding, and decay
- [ ] 02-02-PLAN.md -- Feature computation modules (H2H, form, ranking, fatigue, tournament level)
- [ ] 02-03-PLAN.md -- Sentiment pipeline (RSS/transcript fetching, DistilBERT scoring, DB storage)
- [ ] 02-04-PLAN.md -- Feature builder, refresh runner, APScheduler, and end-to-end integration

### Phase 3: Baseline Model & EV Framework
**Goal**: A calibrated logistic regression model produces match win probabilities and the system calculates expected value against devigged bookmaker odds, with ROI and calibration metrics available
**Depends on**: Phase 2
**Requirements**: MOD-01, MOD-05, ODDS-01, ODDS-02, ODDS-03, ODDS-04
**Success Criteria** (what must be TRUE):
  1. The logistic regression model outputs calibrated probabilities (not raw scores) -- a Platt-scaling or isotonic calibration wrapper is applied
  2. Brier score and log loss are reported as the primary model quality metrics, not accuracy
  3. After importing bookmaker odds, both sides of any match sum to exactly 1.0 +/- 0.001 -- devigging is applied before any EV calculation
  4. The system calculates EV per match as `(p_model x decimal_odds) - 1` and the sign indicates whether a bet has positive or negative expected value
  5. User can enter bookmaker odds via CSV import or manual entry in the dashboard
**Plans:** 3/3 plans complete
Plans:
- [ ] 03-01-PLAN.md -- Dependencies, schema (match_odds + predictions tables), odds ingestion pipeline (CSV, devig, fuzzy linker)
- [ ] 03-02-PLAN.md -- Logistic regression training pipeline with calibration, time-decay weights, and Brier/log-loss metrics
- [ ] 03-03-PLAN.md -- Predictor with EV calculation, prediction storage, and CLI for odds entry and model operations

### Phase 4: Backtesting Engine
**Goal**: Walk-forward backtesting validates historical profitability with Kelly bet sizing, and backtest results are inspectable before any frontend code is written
**Depends on**: Phase 3
**Requirements**: BACK-01, BACK-02, BACK-03, BACK-04, BANK-01, BANK-02
**Success Criteria** (what must be TRUE):
  1. The backtest uses walk-forward splits (train on years 1-N, test on year N+1) -- k-fold shuffling is not used on temporal data
  2. ROI is reported broken down by surface (hard, clay, grass), tournament level (Grand Slam, Masters 1000, ATP 500, ATP 250), and model
  3. Calibration plots (predicted probability buckets vs. empirical win rates) are generated and visually inspectable as image files or printed charts
  4. No feature computed in the backtesting pipeline uses data from the test period -- a dedicated look-ahead bias check passes
  5. Bet sizing uses fractional Kelly (default 0.25x) with a configurable hard cap; full Kelly is never the default
  6. Maximum bet size cap is enforced -- no single bet exceeds the configured ceiling regardless of Kelly output
**Plans:** 1/2 plans executed
Plans:
- [ ] 04-01-PLAN.md -- Schema migration, Kelly bet sizing, walk-forward fold engine with look-ahead bias prevention
- [ ] 04-02-PLAN.md -- ROI breakdowns, calibration plots, bankroll curve, CLI runner

### Phase 5: FastAPI Backend
**Goal**: A running FastAPI server exposes all model predictions, backtest results, analytics, and data entry endpoints over a stable REST API that the frontend can consume
**Depends on**: Phase 4
**Requirements**: DASH-08
**Success Criteria** (what must be TRUE):
  1. `GET /predict`, `GET /backtest`, `GET /bankroll`, `GET /models`, and `GET /props` endpoints return well-formed JSON responses
  2. Model artifacts are loaded once at startup via lifespan context -- no model is trained inside a request-response cycle
  3. The OpenAPI schema at `/docs` accurately documents all request and response shapes with Pydantic v2 types
  4. All database reads use async SQLAlchemy -- no synchronous blocking I/O inside async endpoints
**Plans:** 2/3 plans executed
Plans:
- [ ] 05-01-PLAN.md -- FastAPI skeleton, async SQLAlchemy, Pydantic schemas, job state, test infrastructure
- [ ] 05-02-PLAN.md -- Read endpoints (predict, backtest, bankroll, models, calibration, props stub)
- [ ] 05-03-PLAN.md -- Write/action endpoints (odds entry, CSV upload, props entry, refresh, backtest run)

### Phase 6: React Dashboard Core
**Goal**: The React dashboard visualizes all validated backtest metrics, calibration plots, ROI breakdowns, model comparisons, and active EV signals via the FastAPI backend
**Depends on**: Phase 5
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06
**Success Criteria** (what must be TRUE):
  1. User can view the bankroll curve over time as a line chart on the dashboard
  2. User can view ROI broken down by surface, tournament level, model, and time period as bar charts
  3. User can view calibration reliability diagrams per model -- this chart is prominently placed on the main dashboard view, not buried
  4. User can view a model comparison table showing per-model Brier score, calibration quality, and ROI
  5. User can view active EV signals with model confidence, expected value, and recommended Kelly stake
**Plans:** 6/6 plans complete
Plans:
- [ ] 06-01-PLAN.md -- Scaffold Vite + React + TS project, install deps, Tailwind v3 dark theme, API client + types, app shell with 4-tab nav
- [ ] 06-02-PLAN.md -- Overview tab: KPI cards, bankroll equity curve (Lightweight Charts), calibration diagram (Nivo), DASH-04 placeholder
- [ ] 06-03-PLAN.md -- Backtest tab: 5 ROI bar charts, filter bar, paginated bet history table, click-to-filter interaction
- [ ] 06-04-PLAN.md -- Models tab (comparison table + calibration) and Signals tab (card grid with EV color coding)
- [ ] 06-05-PLAN.md -- Integration: refresh flow, error boundary, bankroll date popover, skeleton loaders, visual verification
- [ ] 06-06-PLAN.md -- Gap closure: wire Brier Score KPI to useModels() hook in OverviewTab

### Phase 7: Advanced Models & Ensemble
**Goal**: GBM and Bayesian models are trained and validated, and a weighted ensemble replaces the single logistic regression baseline as the primary prediction source
**Depends on**: Phase 6
**Requirements**: MOD-02, MOD-03, MOD-04
**Success Criteria** (what must be TRUE):
  1. The XGBoost model outputs calibrated probabilities -- an isotonic calibration wrapper is applied post-training
  2. The Bayesian model (PyMC) produces credible intervals for each match prediction, not just a point estimate
  3. The ensemble blends all available models weighted by inverse Brier score on the validation set -- no model is hard-coded with a fixed weight
  4. Adding a new model to the ensemble does not require changes to the betting or EV calculation logic
**Plans:** 4/4 plans complete
Plans:
- [ ] 07-01-PLAN.md -- Model registry refactor: base.py + logistic.py + trainer.py shim, MODEL_REGISTRY, schema migration (p5/p50/p95)
- [ ] 07-02-PLAN.md -- XGBoost model with Optuna hyperparameter tuning and dual calibration
- [ ] 07-03-PLAN.md -- Bayesian hierarchical logistic model (PyMC) with surface partial pooling and credible intervals
- [ ] 07-04-PLAN.md -- Ensemble blending (inverse Brier weights) and walk-forward multi-model support

### Phase 8: Player Props
**Goal**: The system predicts player stat distributions for PrizePicks props, users can enter prop lines manually, and the system identifies value bets by comparing predictions to entered lines
**Depends on**: Phase 7
**Requirements**: PROP-01, PROP-02, PROP-03
**Success Criteria** (what must be TRUE):
  1. The system produces a predicted distribution (mean and confidence interval) for aces, games won, and double faults per player per match
  2. User can enter a PrizePicks prop line (player, stat, over/under threshold) via the dashboard and see whether the model prediction shows value
  3. The dashboard displays prop prediction accuracy tracked over time as directional validation (model direction vs. actual outcome)
**Plans:** 3 plans
Plans:
- [ ] 08-01-PLAN.md -- PROP_REGISTRY, score parser, base utilities, Poisson/NegBin stat models (aces, double_faults, games_won), CLI
- [ ] 08-02-PLAN.md -- API endpoints (GET /props, GET /props/accuracy), prop resolver, refresh pipeline integration
- [ ] 08-03-PLAN.md -- Props dashboard tab: entry form, PMF chart, value badges, accuracy KPIs, hit rate + calibration charts

### Phase 9: Simulation, Signals & Paper Trading
**Goal**: Monte Carlo bankroll simulation quantifies ruin risk, automated signal generation identifies value bets above a configurable EV threshold, and the paper trading engine tracks fake-money P&L over time
**Depends on**: Phase 8
**Requirements**: BANK-03, BANK-04, SIG-01, SIG-02, SIG-03, SIG-04, DASH-07
**Success Criteria** (what must be TRUE):
  1. User can run a Monte Carlo simulation (1,000-10,000 seasons) and view P(ruin), expected terminal bankroll, and confidence band fan chart on the dashboard
  2. Sharpe ratio is displayed for each betting strategy alongside ROI -- risk-adjusted comparison is available
  3. The system automatically generates a signal when model EV exceeds a user-configured threshold -- signals appear in the dashboard without manual calculation
  4. User can start a paper trading session with a configurable bankroll (default $1,000) and see all bet history and running P&L
  5. User can enter PrizePicks prop lines and bookmaker odds via a unified manual entry form on the dashboard
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Ingestion & Storage | 3/3 | Complete   | 2026-03-16 |
| 2. Elo Ratings & Feature Engineering | 3/4 | In Progress|  |
| 3. Baseline Model & EV Framework | 3/3 | Complete   | 2026-03-17 |
| 4. Backtesting Engine | 1/2 | In Progress|  |
| 5. FastAPI Backend | 2/3 | In Progress|  |
| 6. React Dashboard Core | 6/6 | Complete   | 2026-03-18 |
| 7. Advanced Models & Ensemble | 4/4 | Complete   | 2026-03-18 |
| 8. Player Props | 0/3 | Not started | - |
| 9. Simulation, Signals & Paper Trading | 0/TBD | Not started | - |
