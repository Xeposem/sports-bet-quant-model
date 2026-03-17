# Requirements: Sports Betting Quant Model

**Defined:** 2026-03-15
**Core Value:** Accurate, data-driven predictions that identify positive expected value betting opportunities in tennis

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Data Pipeline

- [x] **DATA-01**: System ingests and cleans historical ATP match data from Jeff Sackmann's tennis_atp repository
- [x] **DATA-02**: System deduplicates and normalizes match records across all available years
- [x] **DATA-03**: System handles retirement, walkover, and default matches (filter or flag contaminated stats)
- [x] **DATA-04**: System enforces temporal integrity — all features computed only from pre-match data (no look-ahead bias)
- [x] **DATA-05**: System stores processed data in SQLite database with schema supporting future WTA extension

### Elo Ratings

- [x] **ELO-01**: System computes surface-specific Elo ratings (hard, clay, grass) for all ATP players
- [x] **ELO-02**: System applies Elo decay for player inactivity periods
- [x] **ELO-03**: System tracks Elo rating history over time per player per surface

### Feature Engineering

- [x] **FEAT-01**: System computes head-to-head records between players (overall and per-surface)
- [x] **FEAT-02**: System computes recent form features (last N matches win rate, service stats) with sliding window
- [x] **FEAT-03**: System computes player ranking and ranking delta (trend) features
- [x] **FEAT-04**: System computes fatigue/scheduling features (days since last match, sets played in last 7 days)
- [x] **FEAT-05**: System performs sentiment analysis on recent articles to assess player fatigue, form, and injury status
- [x] **FEAT-06**: System computes tournament-level features (Grand Slam, Masters 1000, ATP 500, ATP 250)
- [x] **FEAT-07**: User can manually trigger data refresh via dashboard (match data, bookmaker odds, articles for sentiment)
- [x] **FEAT-08**: System supports optional scheduled data fetching on a configurable interval (match data, odds, articles)

### Match Outcome Models

- [x] **MOD-01**: System trains logistic regression model for match outcome prediction with calibrated probabilities
- [ ] **MOD-02**: System trains gradient boosting model (XGBoost) with isotonic calibration for match outcome prediction
- [ ] **MOD-03**: System trains Bayesian model with credible intervals for match outcome prediction using PyMC
- [ ] **MOD-04**: System provides multi-model ensemble that blends predictions weighted by recent calibration performance
- [x] **MOD-05**: System uses Brier score and log loss as primary model quality metrics (not accuracy)

### Player Prop Models

- [ ] **PROP-01**: System predicts player stat distributions (aces, games won, double faults) for PrizePicks props
- [ ] **PROP-02**: System compares prop predictions against manually entered PrizePicks lines to identify value
- [ ] **PROP-03**: System tracks prop prediction accuracy over time (directional validation)

### Odds & Expected Value

- [ ] **ODDS-01**: System ingests bookmaker match odds (manual entry or CSV import)
- [ ] **ODDS-02**: System removes bookmaker vig (devigging) to compute true implied probabilities
- [ ] **ODDS-03**: System calculates expected value (EV) per bet by comparing model probability to devigged odds
- [ ] **ODDS-04**: User can manually enter PrizePicks player prop lines via the dashboard

### Bet Sizing & Bankroll

- [ ] **BANK-01**: System calculates optimal bet size using fractional Kelly criterion (default 0.25x, configurable)
- [ ] **BANK-02**: System enforces configurable maximum bet size cap
- [ ] **BANK-03**: System runs Monte Carlo bankroll simulations (1,000-10,000 seasons) showing P(ruin), expected terminal bankroll, confidence bands
- [ ] **BANK-04**: System calculates Sharpe ratio for each betting strategy

### Backtesting

- [ ] **BACK-01**: System runs walk-forward backtesting with strict chronological train/test splits
- [ ] **BACK-02**: System reports backtest ROI (total, by surface, by tournament level, by model)
- [ ] **BACK-03**: System generates calibration plots (predicted probability buckets vs empirical win rates)
- [ ] **BACK-04**: System prevents any form of look-ahead bias in backtesting pipeline

### Signal Generation & Paper Trading

- [ ] **SIG-01**: System generates automated signals when model EV exceeds configurable threshold
- [ ] **SIG-02**: System supports paper trading with configurable starting bankroll (default $1,000)
- [ ] **SIG-03**: System tracks paper trading P&L over time with full bet history
- [ ] **SIG-04**: System displays active signals with model confidence, EV, and recommended Kelly stake

### Dashboard & API

- [ ] **DASH-01**: React dashboard displays bankroll curve over time
- [ ] **DASH-02**: React dashboard displays ROI charts (by surface, tournament level, model, time period)
- [ ] **DASH-03**: React dashboard displays calibration plots per model
- [ ] **DASH-04**: React dashboard displays Monte Carlo bankroll simulation results
- [ ] **DASH-05**: React dashboard displays active betting signals with EV and stake recommendations
- [ ] **DASH-06**: React dashboard displays model comparison view (per-model accuracy, calibration, ROI)
- [ ] **DASH-07**: React dashboard provides manual entry forms for bookmaker odds and PrizePicks prop lines
- [ ] **DASH-08**: FastAPI backend serves all model predictions, analytics, and historical data via REST API

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### WTA Integration

- **WTA-01**: System ingests and processes WTA match data from Sackmann repository
- **WTA-02**: System trains separate models for WTA tour
- **WTA-03**: Dashboard supports toggling between ATP and WTA views

### Advanced Analytics

- **ADV-01**: System detects model drift via rolling Brier score / log loss monitoring
- **ADV-02**: System supports tournament-level stratified model training (separate models per tier)
- **ADV-03**: Third-party API integration for PrizePicks line data (OpticOdds/Betstamp)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Automated PrizePicks scraping | TOS explicitly prohibits; account/fund seizure risk |
| Real money betting integration | Regulatory/liability complexity; this is a research tool |
| Real-time match streaming | Requires paid API; different architecture than pre-match |
| Live in-play model | Fundamentally different product category |
| Mobile native app | Web dashboard sufficient; 3x development effort |
| Automated bet execution | No legitimate sportsbook API available |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 1 | Complete |
| DATA-05 | Phase 1 | Complete |
| ELO-01 | Phase 2 | Complete |
| ELO-02 | Phase 2 | Complete |
| ELO-03 | Phase 2 | Complete |
| FEAT-01 | Phase 2 | Complete |
| FEAT-02 | Phase 2 | Complete |
| FEAT-03 | Phase 2 | Complete |
| FEAT-04 | Phase 2 | Complete |
| FEAT-05 | Phase 2 | Complete |
| FEAT-06 | Phase 2 | Complete |
| FEAT-07 | Phase 2 | Complete |
| FEAT-08 | Phase 2 | Complete |
| MOD-01 | Phase 3 | Complete |
| MOD-05 | Phase 3 | Complete |
| ODDS-01 | Phase 3 | Pending |
| ODDS-02 | Phase 3 | Pending |
| ODDS-03 | Phase 3 | Pending |
| ODDS-04 | Phase 3 | Pending |
| BACK-01 | Phase 4 | Pending |
| BACK-02 | Phase 4 | Pending |
| BACK-03 | Phase 4 | Pending |
| BACK-04 | Phase 4 | Pending |
| BANK-01 | Phase 4 | Pending |
| BANK-02 | Phase 4 | Pending |
| DASH-08 | Phase 5 | Pending |
| DASH-01 | Phase 6 | Pending |
| DASH-02 | Phase 6 | Pending |
| DASH-03 | Phase 6 | Pending |
| DASH-04 | Phase 6 | Pending |
| DASH-05 | Phase 6 | Pending |
| DASH-06 | Phase 6 | Pending |
| MOD-02 | Phase 7 | Pending |
| MOD-03 | Phase 7 | Pending |
| MOD-04 | Phase 7 | Pending |
| PROP-01 | Phase 8 | Pending |
| PROP-02 | Phase 8 | Pending |
| PROP-03 | Phase 8 | Pending |
| BANK-03 | Phase 9 | Pending |
| BANK-04 | Phase 9 | Pending |
| SIG-01 | Phase 9 | Pending |
| SIG-02 | Phase 9 | Pending |
| SIG-03 | Phase 9 | Pending |
| SIG-04 | Phase 9 | Pending |
| DASH-07 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 48 total
- Mapped to phases: 48
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-15*
*Last updated: 2026-03-15 after roadmap creation — all 48 v1 requirements mapped*
