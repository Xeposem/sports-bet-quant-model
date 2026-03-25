"""
Feature builder — assembles complete feature rows per player per match.

Combines:
- Glicko-2 surface ratings from player_elo table
- H2H record (overall and surface-specific)
- Rolling form and service statistics
- Ranking and ranking delta
- Fatigue features (days since last match, sets in 7 days)
- Tournament level and surface encoding
- Sentiment score (exponential recency-weighted)

Exports:
- build_feature_row: produce a single feature dict for one player in one match
- build_all_features: process all matches and populate match_features table
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Optional

from src.features.h2h import get_h2h
from src.features.form import compute_rolling_form
from src.features.ranking import get_ranking_features
from src.features.fatigue import get_fatigue_features
from src.features.tourney import encode_tourney_level

logger = logging.getLogger(__name__)

# Default Glicko-2 values for players with no historical data
_DEFAULT_ELO = 1500.0
_DEFAULT_RD = 350.0

SURFACES = ["Hard", "Clay", "Grass", "Overall"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_player_elo(
    conn: sqlite3.Connection,
    player_id: int,
    before_date: str,
) -> dict:
    """
    Retrieve the latest Glicko-2 ratings for a player across all four surfaces,
    using snapshots strictly before before_date.

    Returns a dict with keys:
        elo_hard, elo_hard_rd,
        elo_clay, elo_clay_rd,
        elo_grass, elo_grass_rd,
        elo_overall, elo_overall_rd
    Defaults to (1500, 350) for any surface with no prior snapshot.
    """
    result: dict[str, float] = {}
    sql = """
        SELECT elo_rating, rd
        FROM player_elo
        WHERE player_id = :pid
          AND tour = 'ATP'
          AND surface = :surface
          AND as_of_date < :date
        ORDER BY as_of_date DESC
        LIMIT 1
    """
    for surface in SURFACES:
        row = conn.execute(
            sql, {"pid": player_id, "surface": surface, "date": before_date}
        ).fetchone()
        key = surface.lower()  # "hard", "clay", "grass", "overall"
        if row is not None:
            result[f"elo_{key}"] = float(row[0])
            result[f"elo_{key}_rd"] = float(row[1])
        else:
            result[f"elo_{key}"] = _DEFAULT_ELO
            result[f"elo_{key}_rd"] = _DEFAULT_RD
    return result


def _get_pinnacle_prob(
    conn: sqlite3.Connection,
    tourney_id: str,
    match_num: int,
    tour: str = "ATP",
) -> dict:
    """Return devigged Pinnacle win probabilities for winner and loser.

    Queries match_odds for bookmaker='pinnacle' and applies power method devigging.
    Returns a dict with (None, None, 1) when no Pinnacle odds exist or when odds
    are invalid (ValueError caught internally).
    """
    from src.odds.devig import power_method_devig

    row = conn.execute(
        """
        SELECT decimal_odds_a, decimal_odds_b
        FROM match_odds
        WHERE tourney_id = ? AND match_num = ? AND tour = ? AND bookmaker = 'pinnacle'
        LIMIT 1
        """,
        (tourney_id, match_num, tour),
    ).fetchone()
    if row is None:
        return {"pinnacle_prob_winner": None, "pinnacle_prob_loser": None, "has_no_pinnacle": 1}
    try:
        p_a, p_b = power_method_devig(float(row[0]), float(row[1]))
        return {"pinnacle_prob_winner": p_a, "pinnacle_prob_loser": p_b, "has_no_pinnacle": 0}
    except (ValueError, Exception):
        return {"pinnacle_prob_winner": None, "pinnacle_prob_loser": None, "has_no_pinnacle": 1}


def _get_sentiment(
    conn: sqlite3.Connection,
    player_id: int,
    match_date: str,
) -> Optional[float]:
    """
    Compute recency-weighted sentiment score for a player before match_date.

    Returns None if no articles exist or if sentiment tables are missing.
    """
    try:
        from src.sentiment.store import get_player_articles
        from src.sentiment.scorer import weighted_player_sentiment

        articles = get_player_articles(conn, player_id, match_date)
        if not articles:
            return None
        return weighted_player_sentiment(articles, match_date)
    except Exception as exc:
        logger.debug("Sentiment unavailable for player_id=%s: %s", player_id, exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_feature_row(
    conn: sqlite3.Connection,
    match: dict,
    player_id: int,
    opponent_id: int,
    player_role: str,
) -> dict:
    """
    Assemble a complete feature dict for one player in one match.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.
    match : dict
        Must have keys: tourney_id, match_num, tour, tourney_date, surface, tourney_level.
    player_id : int
        The player whose features to compute (perspective player).
    opponent_id : int
        The opposing player (used for H2H calculations).
    player_role : str
        "winner" or "loser" — recorded in the output dict.

    Returns
    -------
    dict
        Flat dict with all match_features schema columns populated.
    """
    tourney_id = match["tourney_id"]
    match_num = match["match_num"]
    tour = match.get("tour", "ATP")
    match_date = match["tourney_date"]
    surface = match.get("surface")
    tourney_level = match.get("tourney_level")

    # --- Glicko-2 ratings ---
    elo_features = _get_player_elo(conn, player_id, match_date)

    # --- H2H overall ---
    h2h_overall = get_h2h(conn, player_id, opponent_id, match_date)

    # --- H2H surface-specific ---
    h2h_surface = get_h2h(conn, player_id, opponent_id, match_date, surface=surface)

    # --- Rolling form ---
    form = compute_rolling_form(conn, player_id, match_date)

    # --- Ranking ---
    ranking = get_ranking_features(conn, player_id, match_date)

    # --- Fatigue ---
    fatigue = get_fatigue_features(conn, player_id, match_date)

    # --- Sentiment (graceful — None on any error or missing data) ---
    sentiment_score = _get_sentiment(conn, player_id, match_date)

    # --- Pinnacle devigged probability ---
    pinnacle = _get_pinnacle_prob(conn, tourney_id, match_num, tour)

    # --- Assemble feature row ---
    row: dict = {
        # Identity
        "tourney_id": tourney_id,
        "match_num": match_num,
        "tour": tour,
        "player_role": player_role,
        # Glicko-2 ratings
        "elo_hard": elo_features["elo_hard"],
        "elo_hard_rd": elo_features["elo_hard_rd"],
        "elo_clay": elo_features["elo_clay"],
        "elo_clay_rd": elo_features["elo_clay_rd"],
        "elo_grass": elo_features["elo_grass"],
        "elo_grass_rd": elo_features["elo_grass_rd"],
        "elo_overall": elo_features["elo_overall"],
        "elo_overall_rd": elo_features["elo_overall_rd"],
        # H2H (overall)
        "h2h_wins": h2h_overall["p1_wins"],
        "h2h_losses": h2h_overall["p1_losses"],
        # H2H (surface)
        "h2h_surface_wins": h2h_surface["p1_wins"],
        "h2h_surface_losses": h2h_surface["p1_losses"],
        # Rolling form
        "form_win_rate_10": form.get("form_win_rate_10"),
        "form_win_rate_20": form.get("form_win_rate_20"),
        "avg_ace_rate": form.get("avg_ace_rate"),
        "avg_df_rate": form.get("avg_df_rate"),
        "avg_first_pct": form.get("avg_first_pct"),
        "avg_first_won_pct": form.get("avg_first_won_pct"),
        # Ranking
        "ranking": ranking["ranking"],
        "ranking_delta": ranking["ranking_delta"],
        # Fatigue
        "days_since_last": fatigue["days_since_last"],
        "sets_last_7_days": fatigue["sets_last_7_days"],
        # Match context
        "tourney_level": tourney_level,
        "surface": surface,
        # Sentiment
        "sentiment_score": sentiment_score,
        # Pinnacle market probability
        "pinnacle_prob_winner": pinnacle["pinnacle_prob_winner"],
        "pinnacle_prob_loser": pinnacle["pinnacle_prob_loser"],
        "has_no_pinnacle": pinnacle["has_no_pinnacle"],
    }
    return row


def build_all_features(conn: sqlite3.Connection) -> dict:
    """
    Process all matches and populate match_features table.

    Queries all matches joined with tournaments (for surface/level) ordered by
    tourney_date, then by round. For each match, builds two feature rows:
    one for the winner and one for the loser.

    Uses INSERT OR REPLACE so the function is idempotent — re-runs overwrite
    existing rows rather than duplicating them.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection with the full schema applied.

    Returns
    -------
    dict
        {"matches_processed": int, "feature_rows_written": int}
    """
    matches_sql = """
        SELECT
            m.tourney_id,
            m.match_num,
            m.tour,
            m.winner_id,
            m.loser_id,
            m.tourney_date,
            t.surface,
            t.tourney_level
        FROM matches m
        JOIN tournaments t ON m.tourney_id = t.tourney_id AND m.tour = t.tour
        ORDER BY m.tourney_date, m.match_num
    """
    rows = conn.execute(matches_sql).fetchall()

    matches_processed = 0
    feature_rows_written = 0

    for row in rows:
        (tourney_id, match_num, tour, winner_id, loser_id,
         tourney_date, surface, tourney_level) = row

        match_dict = {
            "tourney_id": tourney_id,
            "match_num": match_num,
            "tour": tour,
            "tourney_date": tourney_date,
            "surface": surface,
            "tourney_level": tourney_level,
        }

        for player_id, opponent_id, player_role in [
            (winner_id, loser_id, "winner"),
            (loser_id, winner_id, "loser"),
        ]:
            try:
                feature_row = build_feature_row(
                    conn, match_dict,
                    player_id=player_id,
                    opponent_id=opponent_id,
                    player_role=player_role,
                )
                _insert_feature_row(conn, feature_row)
                feature_rows_written += 1
            except Exception as exc:
                logger.error(
                    "Failed to build feature row for tourney_id=%s match_num=%s role=%s: %s",
                    tourney_id, match_num, player_role, exc,
                )

        matches_processed += 1

    conn.commit()

    return {
        "matches_processed": matches_processed,
        "feature_rows_written": feature_rows_written,
    }


def _insert_feature_row(conn: sqlite3.Connection, row: dict) -> None:
    """
    Insert or replace a feature row into match_features table.
    Uses INSERT OR REPLACE to support idempotent re-runs.
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO match_features (
            tourney_id, match_num, tour, player_role,
            elo_hard, elo_hard_rd,
            elo_clay, elo_clay_rd,
            elo_grass, elo_grass_rd,
            elo_overall, elo_overall_rd,
            h2h_wins, h2h_losses,
            h2h_surface_wins, h2h_surface_losses,
            form_win_rate_10, form_win_rate_20,
            avg_ace_rate, avg_df_rate, avg_first_pct, avg_first_won_pct,
            ranking, ranking_delta,
            days_since_last, sets_last_7_days,
            tourney_level, surface,
            sentiment_score,
            pinnacle_prob_winner, pinnacle_prob_loser, has_no_pinnacle
        ) VALUES (
            :tourney_id, :match_num, :tour, :player_role,
            :elo_hard, :elo_hard_rd,
            :elo_clay, :elo_clay_rd,
            :elo_grass, :elo_grass_rd,
            :elo_overall, :elo_overall_rd,
            :h2h_wins, :h2h_losses,
            :h2h_surface_wins, :h2h_surface_losses,
            :form_win_rate_10, :form_win_rate_20,
            :avg_ace_rate, :avg_df_rate, :avg_first_pct, :avg_first_won_pct,
            :ranking, :ranking_delta,
            :days_since_last, :sets_last_7_days,
            :tourney_level, :surface,
            :sentiment_score,
            :pinnacle_prob_winner, :pinnacle_prob_loser, :has_no_pinnacle
        )
        """,
        row,
    )
