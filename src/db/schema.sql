-- Tennis ATP Quantitative Model — SQLite Schema
-- Supports WTA extensibility via 'tour' column on all tables.
-- All tables use CREATE TABLE IF NOT EXISTS for idempotent creation.
-- Feature stub tables (player_elo) are populated in Phase 2.
--
-- Source: DATA-05 requirement + RESEARCH.md Pattern 4

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Players: biographical data extracted from atp_players.csv
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS players (
    player_id    INTEGER NOT NULL,
    tour         TEXT    NOT NULL DEFAULT 'ATP',
    first_name   TEXT,
    last_name    TEXT,
    hand         TEXT,
    birth_date   TEXT,
    country_code TEXT,
    height_cm    INTEGER,
    PRIMARY KEY (player_id, tour)
);

-- ---------------------------------------------------------------------------
-- Tournaments: one row per tournament-year
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tournaments (
    tourney_id    TEXT NOT NULL,
    tour          TEXT NOT NULL DEFAULT 'ATP',
    tourney_name  TEXT,
    surface       TEXT,
    draw_size     INTEGER,
    tourney_level TEXT,
    tourney_date  TEXT NOT NULL,  -- ISO "YYYY-MM-DD"; used for temporal ordering
    PRIMARY KEY (tourney_id, tour)
);

-- ---------------------------------------------------------------------------
-- Matches: one row per match; walkovers and defaults are excluded at ingest
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS matches (
    tourney_id       TEXT    NOT NULL,
    match_num        INTEGER NOT NULL,
    tour             TEXT    NOT NULL DEFAULT 'ATP',
    winner_id        INTEGER,
    loser_id         INTEGER,
    score            TEXT,
    round            TEXT,
    best_of          INTEGER,
    minutes          INTEGER,
    -- Temporal integrity: tourney_date copied here for fast, index-friendly filtering
    tourney_date     TEXT    NOT NULL,  -- ISO "YYYY-MM-DD"
    -- Retirement handling (see CONTEXT.md and RESEARCH.md Pattern 2 + 3)
    match_type       TEXT    NOT NULL DEFAULT 'completed', -- completed/retirement/walkover/default
    retirement_flag  INTEGER NOT NULL DEFAULT 0,           -- 1 if match_type = 'retirement'
    stats_normalized INTEGER NOT NULL DEFAULT 0,           -- 1 if retirement stats were scaled
    -- Data quality flag for downstream model filtering
    stats_missing    INTEGER NOT NULL DEFAULT 0,           -- 1 if core serve stats are absent
    PRIMARY KEY (tourney_id, match_num, tour),
    FOREIGN KEY (tourney_id, tour) REFERENCES tournaments(tourney_id, tour)
);

-- ---------------------------------------------------------------------------
-- Match stats: per-player serve/return statistics in a tall (2 rows/match) format
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS match_stats (
    tourney_id  TEXT    NOT NULL,
    match_num   INTEGER NOT NULL,
    tour        TEXT    NOT NULL DEFAULT 'ATP',
    player_role TEXT    NOT NULL,  -- 'winner' or 'loser'
    ace         INTEGER,
    df          INTEGER,
    svpt        INTEGER,
    first_in    INTEGER,
    first_won   INTEGER,
    second_won  INTEGER,
    sv_gms      INTEGER,
    bp_saved    INTEGER,
    bp_faced    INTEGER,
    PRIMARY KEY (tourney_id, match_num, tour, player_role),
    FOREIGN KEY (tourney_id, match_num, tour) REFERENCES matches(tourney_id, match_num, tour)
);

-- ---------------------------------------------------------------------------
-- Rankings: weekly ATP ranking snapshots from atp_rankings_*.csv
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rankings (
    ranking_date   TEXT    NOT NULL,  -- ISO "YYYY-MM-DD"
    tour           TEXT    NOT NULL DEFAULT 'ATP',
    player_id      INTEGER NOT NULL,
    ranking        INTEGER NOT NULL,
    ranking_points INTEGER,
    PRIMARY KEY (ranking_date, tour, player_id)
);

-- ---------------------------------------------------------------------------
-- Ingestion log: tracks incremental ingestion state per source file
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingestion_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ingested_at    TEXT    NOT NULL,
    source_file    TEXT    NOT NULL,
    tour           TEXT    NOT NULL DEFAULT 'ATP',
    year           INTEGER,
    rows_processed INTEGER,
    rows_inserted  INTEGER,
    rows_skipped   INTEGER,
    status         TEXT    NOT NULL  -- 'success', 'partial', 'failed'
);

-- ---------------------------------------------------------------------------
-- Player Elo: Glicko-2 ratings per player per surface per week
-- Populated by Phase 2 feature engineering (src/ratings/glicko.py)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS player_elo (
    player_id        INTEGER NOT NULL,
    tour             TEXT    NOT NULL DEFAULT 'ATP',
    surface          TEXT    NOT NULL,   -- 'Hard', 'Clay', 'Grass', 'Overall'
    as_of_date       TEXT    NOT NULL,   -- ISO "YYYY-MM-DD" end of ISO week
    elo_rating       REAL    NOT NULL DEFAULT 1500.0,
    rd               REAL    NOT NULL DEFAULT 350.0,    -- Glicko-2 rating deviation
    volatility       REAL    NOT NULL DEFAULT 0.06,     -- Glicko-2 volatility
    matches_played   INTEGER NOT NULL DEFAULT 0,
    last_played_date TEXT,               -- ISO "YYYY-MM-DD" most recent match on this surface
    PRIMARY KEY (player_id, tour, surface, as_of_date)
);

-- ---------------------------------------------------------------------------
-- Match Features: wide format feature row per player per match
-- One row per (player_role: 'winner'/'loser') per match
-- Populated in Phase 2 after Glicko-2 ratings are computed
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS match_features (
    tourney_id              TEXT    NOT NULL,
    match_num               INTEGER NOT NULL,
    tour                    TEXT    NOT NULL DEFAULT 'ATP',
    player_role             TEXT    NOT NULL,  -- 'winner' or 'loser'
    -- Glicko-2 surface-specific ratings at match time (pre-match snapshot)
    elo_hard                REAL,
    elo_hard_rd             REAL,
    elo_clay                REAL,
    elo_clay_rd             REAL,
    elo_grass               REAL,
    elo_grass_rd            REAL,
    elo_overall             REAL,
    elo_overall_rd          REAL,
    -- Head-to-head history
    h2h_wins                INTEGER,
    h2h_losses              INTEGER,
    h2h_surface_wins        INTEGER,
    h2h_surface_losses      INTEGER,
    -- Rolling form (last N matches)
    form_win_rate_10        REAL,
    form_win_rate_20        REAL,
    -- Service stat averages (rolling)
    avg_ace_rate            REAL,
    avg_df_rate             REAL,
    avg_first_pct           REAL,
    avg_first_won_pct       REAL,
    -- Ranking features
    ranking                 INTEGER,
    ranking_delta           INTEGER,  -- change from previous week
    -- Fatigue features
    days_since_last         INTEGER,
    sets_last_7_days        INTEGER,
    -- Match context
    tourney_level           TEXT,
    surface                 TEXT,
    round_ordinal           INTEGER,  -- R128=1, R64=2, R32=3, R16=4, QF=5, SF=6, F=7
    best_of                 INTEGER,  -- 3 or 5
    -- Sentiment
    sentiment_score         REAL,
    -- Pinnacle devigged market probability (NULL when no Pinnacle odds exist)
    pinnacle_prob_winner    REAL,
    pinnacle_prob_loser     REAL,
    has_no_pinnacle         INTEGER,
    PRIMARY KEY (tourney_id, match_num, tour, player_role),
    FOREIGN KEY (tourney_id, match_num, tour) REFERENCES matches(tourney_id, match_num, tour)
);

-- ---------------------------------------------------------------------------
-- Articles: tennis press conference transcripts and news articles
-- Source: ASAPSports, RSS feeds, Cornell tennis interview dataset
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS articles (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id      INTEGER NOT NULL,
    tour           TEXT    NOT NULL DEFAULT 'ATP',
    source         TEXT,           -- 'asapsports', 'rss', 'cornell', etc.
    url            TEXT    UNIQUE, -- deduplicate by URL
    title          TEXT,
    content        TEXT,
    published_date TEXT,           -- ISO "YYYY-MM-DD"
    fetched_at     TEXT            -- ISO "YYYY-MM-DDTHH:MM:SSZ"
);

-- ---------------------------------------------------------------------------
-- Article Sentiment: scored sentiment output per article
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS article_sentiment (
    article_id      INTEGER NOT NULL,
    player_id       INTEGER NOT NULL,
    tour            TEXT    NOT NULL DEFAULT 'ATP',
    sentiment_score REAL,          -- [-1.0, 1.0] normalized score
    keywords_found  TEXT,          -- JSON array of matched tennis keywords
    scored_at       TEXT,          -- ISO "YYYY-MM-DDTHH:MM:SSZ"
    PRIMARY KEY (article_id),
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

-- ---------------------------------------------------------------------------
-- Match Odds: bookmaker decimal odds per match, per bookmaker
-- Populated by Phase 3 odds ingester (CSV import or manual entry)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS match_odds (
    tourney_id       TEXT    NOT NULL,
    match_num        INTEGER NOT NULL,
    tour             TEXT    NOT NULL DEFAULT 'ATP',
    bookmaker        TEXT    NOT NULL DEFAULT 'pinnacle',
    decimal_odds_a   REAL    NOT NULL,  -- odds for player A (winner)
    decimal_odds_b   REAL    NOT NULL,  -- odds for player B (loser)
    source           TEXT    NOT NULL,  -- 'csv' or 'manual'
    imported_at      TEXT    NOT NULL,  -- ISO datetime
    PRIMARY KEY (tourney_id, match_num, tour, bookmaker),
    FOREIGN KEY (tourney_id, match_num, tour) REFERENCES matches(tourney_id, match_num, tour)
);

CREATE INDEX IF NOT EXISTS idx_match_odds_pk
    ON match_odds(tourney_id, match_num, tour);

-- ---------------------------------------------------------------------------
-- Predictions: per-match, per-model probability and EV output
-- Consumed by Phase 4 backtesting, Phase 6 dashboard, Phase 9 signals
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS predictions (
    tourney_id            TEXT    NOT NULL,
    match_num             INTEGER NOT NULL,
    tour                  TEXT    NOT NULL DEFAULT 'ATP',
    player_id             INTEGER NOT NULL,
    model_version         TEXT    NOT NULL,   -- e.g. 'logistic_v1'
    model_prob            REAL,               -- raw logistic output before calibration
    calibrated_prob       REAL,               -- probability after Platt/isotonic calibration
    brier_contribution    REAL,               -- (calibrated_prob - outcome)^2 for this match
    log_loss_contribution REAL,               -- per-match log loss contribution
    pinnacle_prob         REAL,               -- devigged Pinnacle implied probability (NULL if no odds)
    decimal_odds          REAL,               -- Pinnacle decimal odds for this player
    ev_value              REAL,               -- (calibrated_prob * decimal_odds) - 1 (NULL if no odds)
    edge                  REAL,               -- calibrated_prob - pinnacle_prob (NULL if no odds)
    p5                    REAL,               -- Bayesian 5th percentile (90% CI lower bound, NULL for non-Bayesian)
    p50                   REAL,               -- Bayesian 50th percentile (median, NULL for non-Bayesian)
    p95                   REAL,               -- Bayesian 95th percentile (90% CI upper bound, NULL for non-Bayesian)
    predicted_at          TEXT    NOT NULL,   -- ISO datetime
    PRIMARY KEY (tourney_id, match_num, tour, player_id, model_version),
    FOREIGN KEY (tourney_id, match_num, tour) REFERENCES matches(tourney_id, match_num, tour)
);

CREATE INDEX IF NOT EXISTS idx_predictions_model
    ON predictions(model_version, tourney_id, tour);
CREATE INDEX IF NOT EXISTS idx_predictions_ev
    ON predictions(ev_value, model_version)
    WHERE ev_value IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Indexes: optimized for temporal query patterns used in Phase 2 feature engineering
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_matches_date        ON matches(tourney_date, tour);
CREATE INDEX IF NOT EXISTS idx_matches_winner      ON matches(winner_id, tourney_date, tour);
CREATE INDEX IF NOT EXISTS idx_matches_loser       ON matches(loser_id, tourney_date, tour);
CREATE INDEX IF NOT EXISTS idx_rankings_player     ON rankings(player_id, ranking_date, tour);
CREATE INDEX IF NOT EXISTS idx_articles_player     ON articles(player_id, published_date, tour);
CREATE INDEX IF NOT EXISTS idx_match_features_pk   ON match_features(tourney_id, match_num, tour, player_role);

-- ---------------------------------------------------------------------------
-- Backtest Results: per-match, per-fold backtesting output with Kelly sizing
-- Populated by Phase 4 walk-forward backtesting engine
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_results (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    fold_year        INTEGER NOT NULL,
    tourney_id       TEXT    NOT NULL,
    match_num        INTEGER NOT NULL,
    tour             TEXT    NOT NULL DEFAULT 'ATP',
    model_version    TEXT    NOT NULL,
    player_id        INTEGER NOT NULL,
    outcome          INTEGER NOT NULL,
    calibrated_prob  REAL    NOT NULL,
    decimal_odds     REAL    NOT NULL,
    ev               REAL    NOT NULL,
    kelly_full       REAL    NOT NULL,
    kelly_bet        REAL    NOT NULL,
    flat_bet         REAL    NOT NULL DEFAULT 1.0,
    pnl_kelly        REAL    NOT NULL,
    pnl_flat         REAL    NOT NULL,
    bankroll_before  REAL    NOT NULL,
    bankroll_after   REAL    NOT NULL,
    surface          TEXT,
    tourney_level    TEXT,
    winner_rank      INTEGER,
    loser_rank       INTEGER,
    tourney_date     TEXT    NOT NULL,
    UNIQUE (tourney_id, match_num, tour, player_id, model_version)
);

CREATE TABLE IF NOT EXISTS calibration_data (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    fold_label     TEXT NOT NULL,
    model_version  TEXT NOT NULL,
    bin_midpoints  TEXT NOT NULL,
    empirical_freq TEXT NOT NULL,
    n_samples      INTEGER NOT NULL,
    computed_at    TEXT NOT NULL,
    UNIQUE (fold_label, model_version)
);

CREATE INDEX IF NOT EXISTS idx_backtest_results_fold
    ON backtest_results(fold_year, model_version);
CREATE INDEX IF NOT EXISTS idx_backtest_results_ev
    ON backtest_results(ev, model_version)
    WHERE kelly_bet > 0;

-- ---------------------------------------------------------------------------
-- Prop Lines: manual PrizePicks line entry (TOS prohibits scraping)
-- Populated via POST /api/v1/props endpoint
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prop_lines (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tour            TEXT    NOT NULL DEFAULT 'ATP',
    player_id       INTEGER,
    player_name     TEXT    NOT NULL,
    stat_type       TEXT    NOT NULL,
    line_value      REAL    NOT NULL,
    direction       TEXT    NOT NULL,
    match_date      TEXT    NOT NULL,
    bookmaker       TEXT    NOT NULL DEFAULT 'prizepicks',
    entered_at      TEXT    NOT NULL
);

-- ---------------------------------------------------------------------------
-- Prop Predictions: per-player, per-match PMF output from prop GLM models
-- Populated by src/props/__main__.py predict subcommand
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prop_predictions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tour            TEXT    NOT NULL DEFAULT 'ATP',
    player_id       INTEGER NOT NULL,
    player_name     TEXT    NOT NULL,
    stat_type       TEXT    NOT NULL,
    tourney_id      TEXT,
    match_num       INTEGER,
    match_date      TEXT    NOT NULL,
    mu              REAL    NOT NULL,
    pmf_json        TEXT    NOT NULL,
    model_version   TEXT    NOT NULL,
    predicted_at    TEXT    NOT NULL,
    actual_value    INTEGER,
    resolved_at     TEXT,
    UNIQUE (tour, player_id, stat_type, match_date)
);

CREATE INDEX IF NOT EXISTS idx_prop_predictions_date
    ON prop_predictions(match_date, stat_type, tour);

-- ---------------------------------------------------------------------------
-- Signals: persisted prediction signals with user-facing status
-- Populated by GET /signals upsert; status managed via PATCH /signals/{id}/status
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tour            TEXT    NOT NULL DEFAULT 'ATP',
    tourney_id      TEXT    NOT NULL,
    match_num       INTEGER NOT NULL,
    player_id       INTEGER NOT NULL,
    model_version   TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'new',
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    UNIQUE (tourney_id, match_num, tour, player_id, model_version),
    FOREIGN KEY (tourney_id, match_num, tour) REFERENCES matches(tourney_id, match_num, tour)
);

CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status, tour);

-- ---------------------------------------------------------------------------
-- Paper Trading Sessions: single active session at a time
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS paper_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tour            TEXT    NOT NULL DEFAULT 'ATP',
    initial_bankroll REAL   NOT NULL DEFAULT 1000.0,
    current_bankroll REAL   NOT NULL DEFAULT 1000.0,
    kelly_fraction  REAL    NOT NULL DEFAULT 0.25,
    ev_threshold    REAL    NOT NULL DEFAULT 0.0,
    started_at      TEXT    NOT NULL,
    reset_at        TEXT,
    active          INTEGER NOT NULL DEFAULT 1
);

-- ---------------------------------------------------------------------------
-- Paper Bets: individual bets placed within a paper trading session
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS paper_bets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL,
    tour            TEXT    NOT NULL DEFAULT 'ATP',
    tourney_id      TEXT    NOT NULL,
    match_num       INTEGER NOT NULL,
    player_id       INTEGER NOT NULL,
    model_version   TEXT    NOT NULL,
    calibrated_prob REAL    NOT NULL,
    decimal_odds    REAL    NOT NULL,
    ev_value        REAL    NOT NULL,
    kelly_stake     REAL    NOT NULL,
    bankroll_before REAL    NOT NULL,
    bankroll_after  REAL,
    outcome         INTEGER,
    pnl             REAL,
    placed_at       TEXT    NOT NULL,
    resolved_at     TEXT,
    result_source   TEXT,
    FOREIGN KEY (session_id) REFERENCES paper_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_paper_bets_session ON paper_bets(session_id, placed_at);

-- ---------------------------------------------------------------------------
-- Simulation Results: last Monte Carlo simulation (overwritten on each run)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS simulation_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    n_seasons       INTEGER NOT NULL,
    initial_bankroll REAL   NOT NULL,
    kelly_fraction  REAL    NOT NULL,
    ev_threshold    REAL    NOT NULL,
    p_ruin          REAL    NOT NULL,
    expected_terminal REAL  NOT NULL,
    sharpe_ratio    REAL    NOT NULL,
    paths_json      TEXT    NOT NULL,
    terminal_json   TEXT    NOT NULL,
    computed_at     TEXT    NOT NULL
);
