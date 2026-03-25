# Sports Bet Quant Model

Quantitative tennis betting platform with ATP data ingestion, ML-driven probability estimation, expected value analysis, walk-forward backtesting, and a React dashboard for visualization and paper trading.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Data Pipeline](#data-pipeline)
- [Models](#models)
- [Backtesting](#backtesting)
- [API Reference](#api-reference)
- [Dashboard](#dashboard)
- [Paper Trading & Signals](#paper-trading--signals)
- [Monte Carlo Simulation](#monte-carlo-simulation)
- [Player Props](#player-props)
- [Configuration](#configuration)
- [Testing](#testing)
- [Project Structure](#project-structure)

## Overview

The system identifies positive expected value (EV) betting opportunities in ATP tennis by:

1. Ingesting ATP match data from TennisMyLife (stats.tennismylife.org)
2. Computing surface-specific Glicko-2 Elo ratings
3. Engineering 27+ pairwise features (H2H, form, fatigue, serve stats, sentiment)
4. Training calibrated ML models (logistic regression, XGBoost, Bayesian GLM, ensemble)
5. Running walk-forward backtests with Kelly criterion bet sizing
6. Surfacing positive-EV signals on a React dashboard
7. Supporting paper trading to track simulated P&L without real money

## Architecture

```
              ┌─────────────────┐
              │  TennisMyLife   │
              │ (stats.tml.org) │
              └────────┬────────┘
                       │
                ┌──────▼──────┐
                │  Ingestion  │
                │  Pipeline   │
                └──────┬──────┘
                         │
              ┌──────────▼──────────┐
              │     SQLite DB       │
              │  (data/tennis.db)   │
              └──────────┬──────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
   ┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐
   │  Glicko-2   │ │ Feature  │ │  Sentiment  │
   │  Ratings    │ │ Builder  │ │  Scoring    │
   └──────┬──────┘ └────┬─────┘ └──────┬──────┘
          │              │              │
          └──────────────┼──────────────┘
                         │
              ┌──────────▼──────────┐
              │   ML Models         │
              │ (Logistic, XGB,     │
              │  Bayesian, Ensemble)│
              └──────────┬──────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
   ┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐
   │  Backtest   │ │ FastAPI  │ │   Props     │
   │  Engine     │ │  Server  │ │   Models    │
   └─────────────┘ └────┬─────┘ └─────────────┘
                         │
              ┌──────────▼──────────┐
              │   React Dashboard   │
              │  (Vite + TailwindCSS│
              │   + Lightweight     │
              │     Charts)         │
              └─────────────────────┘
```

## Prerequisites

- **Python 3.12+** (required for PyMC v5 compatibility)
- **Node.js 18+** and npm (for the dashboard)
- **Git** (to clone the repository)

## Installation

### 1. Clone and set up Python environment

```bash
git clone <repo-url>
cd sports-bet-quant-model

python -m venv venv
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

pip install -e ".[dev]"
```

### 2. Install frontend dependencies

```bash
cd dashboard
npm install
cd ..
```

### 3. Initialize the database

The database is created automatically on first ingestion. To ingest ATP data from TennisMyLife:

```bash
python -m src.ingestion --start-year 2010
```

This downloads TennisMyLife ATP CSV files and loads players, tournaments, matches, and match stats into `data/tennis.db`.

### 4. Build ratings, features, and sentiment

Ratings, features, and sentiment are built together via the refresh pipeline:

```bash
python -m src.refresh
```

This runs all pipeline steps in order: ingest new data, compute Glicko-2 ratings, fetch articles and score sentiment, and rebuild the match feature matrix.

### 5. Train a model

```bash
python -m src.odds.cli train --output-dir models
```

## Quick Start

After installation, run the API and dashboard:

```bash
# Terminal 1: Start the API server
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Start the dashboard
cd dashboard
npm run dev
```

Open http://localhost:5173 to access the dashboard.

## Data Pipeline

### Ingestion

```bash
# Full ingestion from 2010 onward
python -m src.ingestion --start-year 2010

# Ingest recent years only
python -m src.ingestion --start-year 2024

# Validate data integrity without ingesting
python -m src.ingestion --validate-only

# Force re-ingestion (overwrites existing data)
python -m src.ingestion --force
```

Data flows through these stages:

1. **Download** -- Fetches CSV files from TennisMyLife (stats.tennismylife.org)
2. **Parse & Load** -- Normalizes into players, tournaments, matches, match_stats tables
3. **ID Translation** -- Maps TML alphanumeric player IDs to synthetic integers (>=900000) via SQLite lookup
4. **Deduplicate** -- Handles retirement flags, missing stats, duplicate entries
5. **Ingestion Log** -- Tracks per-file ingestion state for incremental updates

### Daily Refresh

```bash
# One-shot refresh (ratings, odds, articles, sentiment, predictions)
python -m src.refresh

# Scheduled daily refresh at 6:00 AM
python -m src.refresh --schedule --hour 6 --minute 0

# Skip sentiment analysis
python -m src.refresh --no-sentiment
```

The refresh pipeline updates Glicko-2 ratings, imports new odds, fetches tennis articles, scores sentiment, and generates fresh predictions.

### Odds Entry

```bash
# Manual odds entry via interactive CLI
python -m src.odds.cli enter

# Import from tennis-data.co.uk CSV
python -m src.odds.cli import-csv path/to/odds.csv

# Upload odds via API
curl -X POST http://localhost:8000/api/v1/odds/upload -F "file=@odds.csv"
```

## Models

Four model types are available, all registered in a model registry for easy switching:

| Model | Module | Description |
|-------|--------|-------------|
| **Logistic Regression** | `src.model.logistic` | Baseline with auto-selected Platt/isotonic calibration |
| **XGBoost** | `src.model.xgboost_model` | Gradient boosting with the same 27-feature set |
| **Bayesian GLM** | `src.model.bayesian` | PyMC-based, outputs posterior predictive (p5/p50/p95) |
| **Ensemble** | `src.model.ensemble` | Averages/votes across component models |

### Feature Set (27 pairwise differentials)

- Glicko-2 Elo ratings (hard, clay, grass, overall)
- Head-to-head record (wins, losses)
- Recent form (win rate over last 10 and 20 matches)
- Serve statistics (ace rate, double fault rate, first serve %, first serve win %)
- Rankings and ranking delta
- Fatigue indicators (days since last match, sets in last 7 days)
- Surface and tournament level (one-hot encoded)
- Sentiment score (from press conference transcripts)

### Training and Prediction

```bash
# Train logistic model and save
python -m src.odds.cli train --save-path models/logistic_v1.joblib

# Generate predictions with EV values
python -m src.odds.cli predict --model-path models/logistic_v1.joblib
```

### Expected Value Calculation

```
EV = (calibrated_probability x decimal_odds) - 1
```

A prediction with `calibrated_prob = 0.55` and `decimal_odds = 2.10` yields `EV = 0.155` (15.5% edge).

### Kelly Criterion Bet Sizing

```
f* = (b * p - q) / b
```

Where `b = odds - 1`, `p = calibrated probability`, `q = 1 - p`.

Applied with fractional Kelly (default 25%) and a 3% max bankroll cap per bet to manage variance.

## Backtesting

Walk-forward backtesting with chronological year-based folds prevents look-ahead bias:

```bash
# Run backtest with default logistic model
python -m src.backtest.runner

# Specify model version
python -m src.backtest.runner --model-version xgboost_v1

# Specify model version and Kelly fraction
python -m src.backtest.runner --model-version logistic_v1 --kelly-fraction 0.25
```

Each fold:
1. Trains on all data up to fold year
2. Calibrates on validation split
3. Simulates Kelly-sized bets on test year
4. Tracks bankroll evolution per bet

Results are stored in `backtest_results` and viewable on the dashboard Backtest tab.

## API Reference

The FastAPI server runs at `http://localhost:8000`. Interactive docs available at `/docs`.

All routes are prefixed with `/api/v1`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness check with model status |
| `GET` | `/predict` | Positive-EV predictions (filters: model, min_ev, surface, date range) |
| `GET` | `/backtest` | Aggregate backtest summary with ROI breakdowns |
| `GET` | `/backtest/bets` | Paginated individual bet history |
| `POST` | `/backtest/run` | Trigger walk-forward backtest (background job) |
| `GET` | `/backtest/run/status` | Poll backtest job status |
| `GET` | `/models` | Per-model performance metrics |
| `GET` | `/bankroll` | Equity curve with drawdown stats |
| `GET` | `/calibration` | Calibration curve data per fold and model |
| `POST` | `/odds` | Manual odds entry |
| `POST` | `/odds/upload` | Upload odds CSV file |
| `GET` | `/odds/list` | List stored odds |
| `DELETE` | `/odds/{tourney_id}/{match_num}` | Delete an odds entry |
| `GET` | `/props` | Prop predictions with P(over/under) from PMF |
| `GET` | `/props/accuracy` | Prop prediction accuracy and calibration |
| `POST` | `/props/scan` | OCR scan a screenshot to extract prop lines |
| `POST` | `/props` | Enter a PrizePicks prop line (fuzzy player matching) |
| `GET` | `/props/lines` | List manually entered prop lines |
| `DELETE` | `/props/lines/{id}` | Delete a prop line |
| `GET` | `/signals` | Upsert and return filtered signals |
| `PATCH` | `/signals/{id}/status` | Update signal status |
| `GET` | `/paper/session` | Active paper trading session with stats |
| `POST` | `/paper/session` | Create new paper trading session |
| `DELETE` | `/paper/session` | Deactivate current session |
| `POST` | `/paper/bets` | Place a paper bet from a signal |
| `GET` | `/paper/bets` | List bets for active session |
| `PATCH` | `/paper/bets/{id}/resolve` | Resolve a bet with outcome |
| `GET` | `/paper/equity` | Equity curve for active session |
| `POST` | `/simulation/run` | Run Monte Carlo simulation |
| `GET` | `/simulation/result` | Last stored simulation result |
| `POST` | `/refresh` | Trigger data refresh pipeline |
| `GET` | `/refresh/status` | Poll refresh job status |
| `POST` | `/refresh/cancel` | Cancel running refresh job |

## Dashboard

The React dashboard provides six tabs for interacting with the system:

| Tab | What it shows |
|-----|---------------|
| **Overview** | KPI cards, bankroll equity curve, Monte Carlo simulation section |
| **Backtest** | ROI breakdowns by surface/level/year/EV bucket, individual bet table |
| **Models** | Per-model Brier score, log loss, calibration curves |
| **Signals** | Positive-EV predictions with EV threshold slider, signal status tracking |
| **Props** | Player prop predictions with PMF charts, accuracy metrics, prop line entry |
| **Paper Trading** | Session management, paper bet placement, equity curve, bet history |

### Running the Dashboard

```bash
cd dashboard
npm run dev       # Development server at http://localhost:5173
npm run build     # Production build
npm run preview   # Preview production build
```

The dashboard connects to the FastAPI backend at `http://localhost:8000/api/v1` by default.

### Tech Stack

- React 19 + TypeScript 5.9
- Vite 8 for bundling
- TailwindCSS 3.4 for styling
- Radix UI primitives (tabs, dialog, select, popover)
- Lightweight Charts 5.1 for time-series (equity curves, fan charts)
- Nivo 0.99 for statistical charts (bar, scatter)
- TanStack React Query 5 for data fetching

## Paper Trading & Signals

### Signals

The system automatically generates signals when model EV exceeds a configurable threshold. On the Signals tab:

- Adjust the EV threshold slider (0--20%) to filter signals
- Each signal card shows: EV%, probability, Kelly stake, model confidence, Sharpe ratio
- Signal statuses: **new** -> **seen** -> **acted-on** / **expired**

### Paper Trading

Start a paper trading session to track simulated P&L:

1. Go to the **Paper Trading** tab
2. Click **Start Session** with your desired starting bankroll (default $1,000)
3. On the **Signals** tab, click **Place Bet** on any signal card
4. Bets are sized using fractional Kelly criterion
5. Resolve bets manually or wait for auto-resolution on data refresh
6. Track your equity curve and win rate on the Paper Trading tab

No real money is involved. Reset the session at any time to start fresh.

## Monte Carlo Simulation

Run Monte Carlo simulations to quantify bankroll risk:

1. On the **Overview** tab, scroll to the Monte Carlo section
2. Configure parameters:
   - **Seasons**: 1,000--10,000 simulated seasons
   - **Starting bankroll**: Override the default $1,000
   - **Kelly fraction**: Test conservative sizing (0.1x, 0.25x, 0.5x)
   - **EV threshold**: Minimum EV to include a bet
3. Click **Run Simulation**

Results include:
- **P(ruin)**: Probability of going to zero
- **Expected terminal bankroll**: Median outcome
- **Sharpe ratio**: Risk-adjusted return
- **Fan chart**: Percentile paths (5th, 25th, median, 75th, 95th)
- **Histogram**: Terminal bankroll distribution with ruin tail highlighted

## Player Props

Predict player prop outcomes (aces, games won, double faults) using Gaussian GLM models:

```bash
# Train all prop models
python -m src.props train

# Train a specific stat type
python -m src.props train --stat-type aces

# Generate predictions (last 30 days by default)
python -m src.props predict

# Predict for a specific date range
python -m src.props predict --date-from 2025-01-01 --date-to 2025-03-01
```

### Screenshot Scanner

Scan PrizePicks screenshots to extract prop lines automatically:

1. On the **Props** tab, click **Scan Screenshot**
2. Upload an image file or paste from clipboard
3. The OCR scanner extracts player names, stat types, and lines
4. Review the extracted entries and confirm to submit

### Manual Line Entry

Enter PrizePicks prop lines via the dashboard:

1. Click the green **Enter Data** button (floating action button, bottom-right)
2. Toggle between **Match Odds** and **Prop Line**
3. Fill in player name (fuzzy-matched), stat type, line value, direction
4. Click **Save Entry** -- the form stays open for batch entry
5. View and manage entries in the CRUD table below the form

Props predictions show P(over) and P(under) computed from the model's probability mass function (PMF).

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TENNIS_DB` | `data/tennis.db` | Path to SQLite database |
| `MODEL_PATH` | `models/logistic_v1.joblib` | Path to trained model file |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Comma-separated CORS origins |

### Database

SQLite with WAL journal mode for concurrent read performance. The database is created automatically on first ingestion at the `TENNIS_DB` path. Foreign key constraints are enabled.

## Testing

### Python Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run a specific test file
pytest tests/test_api.py

# Run verbose
pytest -v
```

Test suite covers API endpoints, model training/calibration, backtesting logic, Glicko-2 computation, feature engineering, data ingestion, props predictions, signals, paper trading, and Monte Carlo simulation.

### Frontend Tests

```bash
cd dashboard

# Run all tests
npx vitest run

# Run specific test
npx vitest run src/__tests__/SignalCard.test.tsx

# Run with verbose output
npx vitest run --reporter=verbose
```

## Project Structure

```
sports-bet-quant-model/
├── src/
│   ├── api/                      # FastAPI application
│   │   ├── main.py               # App entry point, lifespan, CORS
│   │   ├── schemas.py            # Pydantic request/response models
│   │   └── routers/              # Route handlers
│   │       ├── backtest.py       # Backtest results and triggers
│   │       ├── bankroll.py       # Equity curve
│   │       ├── calibration.py    # Calibration curves
│   │       ├── models.py         # Model performance
│   │       ├── odds.py           # Manual odds entry
│   │       ├── paper.py          # Paper trading session/bets
│   │       ├── predict.py        # Predictions with EV
│   │       ├── props.py          # Props predictions, lines, and screenshot scan
│   │       ├── refresh.py        # Data refresh pipeline trigger
│   │       ├── signals.py        # Signal generation and status
│   │       └── simulation.py     # Monte Carlo simulation
│   ├── backtest/                 # Walk-forward backtesting
│   │   ├── runner.py             # CLI entry point
│   │   ├── walk_forward.py       # Fold-based backtest engine
│   │   ├── kelly.py              # Kelly criterion bet sizing
│   │   ├── monte_carlo.py        # Monte Carlo simulation engine
│   │   └── reporting.py          # Backtest result formatting
│   ├── db/                       # Database layer
│   │   ├── schema.sql            # Full DDL (20 tables)
│   │   ├── connection.py         # SQLite connection management
│   │   └── validation.py         # Data integrity checks
│   ├── features/                 # Feature engineering
│   │   └── builder.py            # 27-feature match feature matrix
│   ├── ingestion/                # Data ingestion pipeline
│   │   ├── __main__.py           # CLI entry point
│   │   ├── loader.py             # Ingest orchestration (ingest_all, ingest_year)
│   │   ├── cleaner.py            # Data cleaning and deduplication
│   │   ├── validator.py          # Data integrity checks
│   │   ├── tml_downloader.py     # TennisMyLife CSV download
│   │   └── tml_id_mapper.py      # TML alphanumeric → synthetic integer ID translation
│   ├── model/                    # ML model implementations
│   │   ├── __init__.py           # Model registry
│   │   ├── base.py               # Shared utilities, save/load
│   │   ├── logistic.py           # Logistic regression + calibration
│   │   ├── xgboost_model.py      # XGBoost gradient boosting
│   │   ├── bayesian.py           # PyMC Bayesian GLM
│   │   ├── ensemble.py           # Multi-model ensemble
│   │   ├── trainer.py            # Training orchestration
│   │   └── predictor.py          # Prediction generation
│   ├── odds/                     # Odds management
│   │   └── cli.py                # CLI for odds entry, training, prediction
│   ├── props/                    # Player props models
│   │   ├── __main__.py           # CLI: train and predict commands
│   │   ├── base.py               # Shared GLM base, predict_and_store
│   │   ├── aces.py               # Aces GLM
│   │   ├── games_won.py          # Games won GLM
│   │   ├── double_faults.py      # Double faults GLM
│   │   ├── scanner.py            # OCR screenshot scanner for prop lines
│   │   ├── resolver.py           # Player name resolution (fuzzy matching)
│   │   └── score_parser.py       # Score string parsing utilities
│   ├── ratings/                  # Rating computation
│   │   └── glicko.py             # Surface-specific Glicko-2
│   ├── refresh/                  # Data refresh pipeline
│   │   └── __main__.py           # Scheduled/one-shot refresh
│   └── sentiment/                # Sentiment analysis
│       └── scorer.py             # Transformer-based scoring
├── dashboard/                    # React frontend
│   ├── src/
│   │   ├── App.tsx               # Root component with FAB
│   │   ├── main.tsx              # Entry point
│   │   ├── api/types.ts          # TypeScript API types
│   │   ├── hooks/                # TanStack Query hooks
│   │   ├── tabs/                 # 6 dashboard tabs
│   │   ├── components/
│   │   │   ├── charts/           # FanChart, HistogramChart, BankrollChart, etc.
│   │   │   ├── layout/           # TabNav, Header
│   │   │   ├── modals/           # ManualEntryModal
│   │   │   ├── shared/           # KpiCard, SignalCard, MonteCarloSection, PropScanPreview
│   │   │   └── ui/               # Radix UI primitives
│   │   └── __tests__/            # Vitest component tests
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── tests/                        # Python test suite
├── data/                         # SQLite DB and raw CSVs (gitignored)
├── models/                       # Trained model artifacts (gitignored)
├── pyproject.toml                # Python package config
└── requirements.txt              # Additional dependencies
```

## License

This project is for educational and research purposes. No real money betting is endorsed or supported.
