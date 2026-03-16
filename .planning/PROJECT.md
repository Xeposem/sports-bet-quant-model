# Sports Betting Quant Model

## What This Is

A quantitative sports betting analysis platform for tennis, starting with ATP. It combines multiple predictive models (Elo, logistic regression, Bayesian, gradient boosting) to predict both match outcomes and player performance props. The system tracks PrizePicks player prop lines (manual entry) and bookmaker match odds, runs backtests against historical data, and provides a React dashboard for visualizing profitability metrics — all using fake money for paper trading.

## Core Value

Accurate, data-driven predictions that identify positive expected value betting opportunities in tennis — measured by demonstrable edge over bookmaker lines in backtesting.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Collect and process historical ATP tennis data (Jeff Sackmann's tennis_atp repo)
- [ ] Build Elo rating system for tennis players
- [ ] Build logistic regression model for match outcome prediction
- [ ] Build Bayesian model for player performance prediction
- [ ] Build gradient boosting model for match/prop prediction
- [ ] Evaluate model profitability using Kelly criterion betting
- [ ] Calculate expected value against bookmaker odds and PrizePicks lines
- [ ] Build bankroll simulation engine with configurable starting bankroll (default $1,000)
- [ ] Build backtesting engine to evaluate models against historical data
- [ ] Manual entry system for PrizePicks player prop lines
- [ ] Ingest and compare against bookmaker match odds
- [ ] Generate ROI vs bookmaker odds analysis
- [ ] Generate calibration plots (predicted vs actual probabilities)
- [ ] Calculate Sharpe ratio for betting strategies
- [ ] Run Monte Carlo bankroll simulations
- [ ] Live line tracking with automated signal generation
- [ ] Paper trading system (fake money, real lines)
- [ ] React frontend dashboard for visualizing all metrics
- [ ] FastAPI backend serving model predictions and analytics

### Out of Scope

- WTA data — deferred to future milestone, architecture should support it
- Real money betting — this is a research/analysis tool only
- Automated scraping of PrizePicks — TOS prohibits it
- Real-time match data streaming — manual line entry is sufficient for v1
- Mobile app — web dashboard only

## Context

- **Data source**: Jeff Sackmann's open-source tennis_atp GitHub repository provides comprehensive historical ATP match data including scores, stats, rankings, and surface information
- **PrizePicks**: Daily fantasy sports platform offering player prop bets (over/under on individual stats like aces, games won, sets). Lines will be manually entered to avoid TOS violations
- **Bookmaker odds**: Publicly available match odds from various sportsbooks for comparison
- **Tennis-specific factors**: Surface type (hard/clay/grass), player fatigue/scheduling, head-to-head records, tournament level, and recent form are all critical predictive features
- **Paper trading**: All betting is simulated with fake money to evaluate strategy profitability without financial risk

## Constraints

- **Data**: Free datasets only (Jeff Sackmann) — no paid APIs for v1
- **PrizePicks lines**: Manual entry only — no scraping or automated collection
- **Stack**: Python (ML/data) + FastAPI (backend) + React (frontend)
- **Tour**: ATP only for v1 — WTA planned for future milestone
- **Money**: Fake money only — no real betting integration

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Manual PrizePicks line entry | TOS explicitly bans scraping; account/fund seizure risk | — Pending |
| Free data sources (Sackmann) | Comprehensive, well-maintained, community standard for tennis analytics | — Pending |
| React + FastAPI stack | Full customizability for dashboard; Python backend natural for ML models | — Pending |
| ATP-first approach | More data available, simpler scope; WTA architecture-ready | — Pending |
| Multiple model approach | Ensemble of Elo + regression + Bayesian + GBM provides model diversity and comparison | — Pending |

---
*Last updated: 2026-03-15 after initialization*
