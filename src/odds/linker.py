"""
Fuzzy match linking: links odds CSV rows to Sackmann match IDs via
tourney_date + player name fuzzy matching.

Uses rapidfuzz for C++-speed token_sort_ratio matching, which handles
name order variants (e.g., "Djokovic N." vs "Novak Djokovic").
"""
import logging
import sqlite3
from datetime import date, timedelta
from typing import Optional

from rapidfuzz import fuzz, process


logger = logging.getLogger(__name__)

# Date window for match lookup: ±3 days from the odds CSV date
_DATE_WINDOW_DAYS = 3


def fuzzy_link_player(
    name: str,
    candidates: list,
    threshold: int = 85,
) -> Optional[str]:
    """
    Fuzzy match a player name against a list of candidate names.

    Uses token_set_ratio which handles:
    - word-order differences ("Federer Roger" vs "Roger Federer")
    - subset name variants ("Novak Djokovic" -> "Djokovic", "Djokovic N.")
    - partial last-name matching ("Djokovic" subset of "Novak Djokovic" -> 100%)

    token_set_ratio is preferred over token_sort_ratio for player name matching
    because it correctly handles cases where the CSV uses only a last name but
    the database has a full "First Last" name.

    Args:
        name: Player name to match (from odds CSV).
        candidates: List of candidate names (from players table).
        threshold: Minimum score to accept a match (default 85).
                   Threshold of 85 is recommended to avoid false positives
                   (see RESEARCH.md Pitfall 5).

    Returns:
        Best matching candidate string if score >= threshold, else None.
    """
    if not candidates:
        return None

    result = process.extractOne(name, candidates, scorer=fuzz.token_set_ratio)
    if result is not None and result[1] >= threshold:
        return result[0]
    return None


def link_odds_to_matches(
    conn: sqlite3.Connection,
    odds_rows: list,
) -> list:
    """
    Link a list of odds CSV rows to Sackmann match IDs.

    For each odds row, queries matches within ±3 days of the match date,
    builds candidate player name list, and fuzzy matches winner and loser names.
    Rows that cannot be linked are returned with tourney_id=None (unlinked).

    Args:
        conn: SQLite connection with schema applied.
        odds_rows: List of dicts with keys: match_date, winner_name, loser_name,
                   decimal_odds_winner, decimal_odds_loser.

    Returns:
        List of dicts — same rows with tourney_id, match_num, tour appended
        when linked; tourney_id=None for unlinked rows.
    """
    results = []

    for row in odds_rows:
        match_date_str = row.get("match_date")
        winner_name = row.get("winner_name", "")
        loser_name = row.get("loser_name", "")

        linked_row = dict(row)
        linked_row["tourney_id"] = None
        linked_row["match_num"] = None
        linked_row["tour"] = None

        if not match_date_str:
            logger.warning("Odds row missing match_date, skipping: %s", row)
            results.append(linked_row)
            continue

        try:
            center_date = date.fromisoformat(match_date_str)
        except ValueError:
            logger.warning("Invalid match_date format '%s', skipping", match_date_str)
            results.append(linked_row)
            continue

        start_date = (center_date - timedelta(days=_DATE_WINDOW_DAYS)).isoformat()
        end_date = (center_date + timedelta(days=_DATE_WINDOW_DAYS)).isoformat()

        # Fetch all matches in the date window with player names
        candidate_rows = conn.execute(
            """
            SELECT
                m.tourney_id, m.match_num, m.tour,
                pw.first_name || ' ' || pw.last_name AS winner_full_name,
                pl.first_name || ' ' || pl.last_name AS loser_full_name,
                pw.last_name AS winner_last_name,
                pl.last_name AS loser_last_name
            FROM matches m
            JOIN players pw ON pw.player_id = m.winner_id AND pw.tour = m.tour
            JOIN players pl ON pl.player_id = m.loser_id AND pl.tour = m.tour
            WHERE m.tourney_date BETWEEN ? AND ?
            """,
            (start_date, end_date),
        ).fetchall()

        if not candidate_rows:
            logger.debug(
                "No matches found in window %s to %s for odds row: %s / %s",
                start_date, end_date, winner_name, loser_name,
            )
            results.append(linked_row)
            continue

        # Build candidate name lists for fuzzy matching.
        # Include both "First Last" and "Last" variants to handle CSV format differences.
        winner_candidates = []
        loser_candidates = []
        candidate_map = {}  # candidate_key -> (tourney_id, match_num, tour)

        for cand in candidate_rows:
            w_full = cand["winner_full_name"]
            l_full = cand["loser_full_name"]
            w_last = cand["winner_last_name"]
            l_last = cand["loser_last_name"]

            key = (cand["tourney_id"], cand["match_num"], cand["tour"])

            if w_full not in winner_candidates:
                winner_candidates.append(w_full)
                candidate_map[("winner", w_full)] = key
            if w_last not in winner_candidates:
                winner_candidates.append(w_last)
                candidate_map[("winner", w_last)] = key

            if l_full not in loser_candidates:
                loser_candidates.append(l_full)
                candidate_map[("loser", l_full)] = key
            if l_last not in loser_candidates:
                loser_candidates.append(l_last)
                candidate_map[("loser", l_last)] = key

        matched_winner = fuzzy_link_player(winner_name, winner_candidates, threshold=85)
        matched_loser = fuzzy_link_player(loser_name, loser_candidates, threshold=85)

        if matched_winner is not None:
            match_key = candidate_map.get(("winner", matched_winner))
            if match_key:
                linked_row["tourney_id"] = match_key[0]
                linked_row["match_num"] = match_key[1]
                linked_row["tour"] = match_key[2]
                logger.debug(
                    "Linked '%s' -> '%s' (match %s/%s)",
                    winner_name, matched_winner, match_key[0], match_key[1],
                )
        elif matched_loser is not None:
            match_key = candidate_map.get(("loser", matched_loser))
            if match_key:
                linked_row["tourney_id"] = match_key[0]
                linked_row["match_num"] = match_key[1]
                linked_row["tour"] = match_key[2]
                logger.debug(
                    "Linked via loser '%s' -> '%s' (match %s/%s)",
                    loser_name, matched_loser, match_key[0], match_key[1],
                )
        else:
            logger.info(
                "Unlinked: no match found for %s / %s on %s",
                winner_name, loser_name, match_date_str,
            )

        results.append(linked_row)

    return results
