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
-- Player Elo: Phase 2 stub — populated by feature engineering phase
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS player_elo (
    player_id      INTEGER NOT NULL,
    tour           TEXT    NOT NULL DEFAULT 'ATP',
    surface        TEXT    NOT NULL,
    as_of_date     TEXT    NOT NULL,  -- ISO "YYYY-MM-DD"
    elo_rating     REAL    NOT NULL DEFAULT 1500.0,
    matches_played INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (player_id, tour, surface, as_of_date)
);

-- ---------------------------------------------------------------------------
-- Indexes: optimized for temporal query patterns used in Phase 2 feature engineering
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_matches_date   ON matches(tourney_date, tour);
CREATE INDEX IF NOT EXISTS idx_matches_winner ON matches(winner_id, tourney_date, tour);
CREATE INDEX IF NOT EXISTS idx_matches_loser  ON matches(loser_id, tourney_date, tour);
CREATE INDEX IF NOT EXISTS idx_rankings_player ON rankings(player_id, ranking_date, tour);
