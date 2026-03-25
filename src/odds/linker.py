"""
Fuzzy match linking: links odds CSV rows to match IDs via
tourney_date + player name fuzzy matching.

Uses rapidfuzz for C++-speed token_sort_ratio matching, which handles
name order variants (e.g., "Djokovic N." vs "Novak Djokovic").
"""
import logging
import re
import sqlite3
from datetime import date, timedelta
from typing import Optional

from rapidfuzz import fuzz, process


logger = logging.getLogger(__name__)

# Pattern to strip abbreviated initials with periods (e.g. "R.", "Zh.")
# Matches 1-2 uppercase letters followed by a period at a word boundary.
_INITIAL_RE = re.compile(r"\b[A-Z][a-z]?\.\s*")


def _normalize_name(name: str) -> str:
    """Normalize a player name for fuzzy matching.

    - Strips abbreviated initials with periods ("Federer R." -> "Federer",
      "Zhang Zh." -> "Zhang") — applied before lowercasing so [A-Z] matches
    - Replaces apostrophes with spaces ("O'Connell" -> "o connell") so it
      matches odds-file format ("O Connell")
    - Lowercases for case-insensitive comparison ("De Jong" == "de Jong")
    - Collapses extra whitespace
    """
    if not name:
        return name or ""
    # Strip initials before lowercasing (regex needs uppercase letters)
    cleaned = _INITIAL_RE.sub(" ", name)
    cleaned = cleaned.replace("'", " ").replace("\u2019", " ")
    # Normalize hyphens to spaces — odds files use hyphens ("Auger-Aliassime")
    # but the DB often stores spaces ("Auger Aliassime") or vice versa.
    cleaned = cleaned.replace("-", " ")
    cleaned = cleaned.lower()
    cleaned = cleaned.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned if cleaned else name.lower()

# Date window for match lookup.
# The DB stores tournament start date for all matches, while odds files have
# the actual match date. Large events (Grand Slams, Shanghai) can span up to
# 18 days, so we look back 21 days to be safe, and forward 3 days for minor
# date discrepancies. False positives are prevented by requiring both player
# names to fuzzy-match.
_DATE_WINDOW_BEFORE = 21
_DATE_WINDOW_AFTER = 3


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

    # Try exact fuzzy match first
    result = process.extractOne(name, candidates, scorer=fuzz.token_set_ratio)
    if result is not None and result[1] >= threshold:
        return result[0]

    # Retry with normalized names (strip initials like "R." from "Federer R.")
    norm_name = _normalize_name(name)
    norm_candidates = [_normalize_name(c) for c in candidates]
    result = process.extractOne(norm_name, norm_candidates, scorer=fuzz.token_set_ratio)
    if result is not None and result[1] >= threshold:
        # Map back to original candidate string
        idx = norm_candidates.index(result[0])
        return candidates[idx]

    return None


def link_odds_to_matches(
    conn: sqlite3.Connection,
    odds_rows: list,
) -> list:
    """
    Link a list of odds CSV rows to match IDs.

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

    try:
        from tqdm import tqdm
        odds_iter = tqdm(odds_rows, desc="Linking odds", unit="row")
    except ImportError:
        odds_iter = odds_rows

    for row in odds_iter:
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

        start_date = (center_date - timedelta(days=_DATE_WINDOW_BEFORE)).isoformat()
        end_date = (center_date + timedelta(days=_DATE_WINDOW_AFTER)).isoformat()

        # Fetch all matches in the date window with player names
        candidate_rows = conn.execute(
            """
            SELECT
                m.tourney_id, m.match_num, m.tour,
                CASE WHEN pw.first_name IS NOT NULL
                     THEN pw.first_name || ' ' || pw.last_name
                     ELSE pw.last_name END AS winner_full_name,
                CASE WHEN pl.first_name IS NOT NULL
                     THEN pl.first_name || ' ' || pl.last_name
                     ELSE pl.last_name END AS loser_full_name,
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

        # Score each candidate match by fuzzy-matching BOTH winner and loser names.
        # This avoids false positives from the wider date window.
        norm_w = _normalize_name(winner_name)
        norm_l = _normalize_name(loser_name)
        best_score = 0
        best_key = None

        for cand in candidate_rows:
            key = (cand["tourney_id"], cand["match_num"], cand["tour"])
            # Try both full name and last name, take the best score for each side
            w_names = [cand["winner_full_name"], cand["winner_last_name"]]
            l_names = [cand["loser_full_name"], cand["loser_last_name"]]

            w_score = max(
                fuzz.token_set_ratio(norm_w, _normalize_name(n or ""))
                for n in w_names
            )
            l_score = max(
                fuzz.token_set_ratio(norm_l, _normalize_name(n or ""))
                for n in l_names
            )

            # Both players must pass threshold. 75 is safe because we
            # require BOTH names to match (not just one), preventing false
            # positives. Needed for multi-word surnames like "De Minaur".
            if w_score >= 75 and l_score >= 75:
                combined = w_score + l_score
                if combined > best_score:
                    best_score = combined
                    best_key = key

        if best_key is not None:
            linked_row["tourney_id"] = best_key[0]
            linked_row["match_num"] = best_key[1]
            linked_row["tour"] = best_key[2]
        else:
            logger.info(
                "Unlinked: no match found for %s / %s on %s",
                winner_name, loser_name, match_date_str,
            )

        results.append(linked_row)

    return results
