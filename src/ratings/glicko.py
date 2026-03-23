"""
Weekly batch Glicko-2 rating engine for tennis ATP matches.

Processes all matches in strict chronological order, grouping by ISO week
to form rating periods. Computes surface-specific (Hard, Clay, Grass) and
Overall Glicko-2 ratings for every player.

Key design decisions:
- Opponent ratings are FROZEN at week-start (no mid-week contamination)
- Four independent surface tracks: Hard, Clay, Grass, Overall
- Retirement matches use fractional outcomes (0.5x reduced outcome deviation)
- Tournament-level weighting: Grand Slams use full outcomes, ATP 250 reduces deviation
- Inactive players receive RD growth (did_not_compete) each missing week
- Additional rating decay toward mean after surface-specific inactivity thresholds
- Full history preserved: one row per (player_id, surface, as_of_date) in player_elo

Usage:
    from src.ratings.glicko import compute_all_ratings
    result = compute_all_ratings(conn)
    # result = {"total_weeks": N, "total_players": M, "total_snapshots": K}
"""

import logging
from datetime import date, timedelta

from glicko2 import Player  # type: ignore
from tqdm import tqdm

from src.ratings.decay import apply_decay_if_needed, SURFACE_THRESHOLDS
from src.ratings.seeder import seed_rating_from_rank

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SURFACES = ["Hard", "Clay", "Grass", "Overall"]

# Round ordering for canonical within-tournament sorting
ROUND_ORDER: dict[str, int] = {
    "ER": 0,
    "R128": 1,
    "R64": 2,
    "R32": 3,
    "R16": 4,
    "QF": 5,
    "RR": 5,
    "BR": 5,
    "SF": 6,
    "F": 7,
}

# Tournament-level weighting for outcome deviation
# Grand Slam (G) = 1.0, Masters (M) = 0.85, ATP500 (A) = 0.70,
# ATP Finals (F) = 0.65, Davis Cup (D) = 0.50, Challenger (C) = 0.50
TOURNEY_WEIGHT: dict[str, float] = {
    "G": 1.0,   # Grand Slam
    "M": 0.85,  # Masters 1000
    "A": 0.70,  # ATP 500 / ATP 250
    "F": 0.65,  # ATP Finals
    "D": 0.50,  # Davis Cup
    "C": 0.50,  # Challenger
}
_DEFAULT_TOURNEY_WEIGHT = 0.70

# Retirement match: reduce outcome deviation by this multiplier
RETIREMENT_MULT = 0.5

# Default Glicko-2 initial values
DEFAULT_RATING = 1500.0
DEFAULT_RD = 350.0
DEFAULT_VOL = 0.06


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _get_iso_week(date_str: str) -> tuple:
    """
    Return (year, week_number) ISO week tuple from an ISO date string.

    Parameters
    ----------
    date_str : str
        Date in ISO "YYYY-MM-DD" format.

    Returns
    -------
    tuple[int, int]
        (iso_year, iso_week) per ISO 8601 calendar.
    """
    d = date.fromisoformat(date_str)
    iso = d.isocalendar()
    return (iso[0], iso[1])


def _get_week_end_date(year: int, week: int) -> str:
    """
    Return the ISO Sunday date for a given (year, week) as YYYY-MM-DD.
    """
    # ISO week starts on Monday; day 7 = Sunday
    d = date.fromisocalendar(year, week, 7)
    return d.isoformat()


def _load_matches_ordered(conn) -> list:
    """
    Query all completed/retirement matches with tournament surface info.

    Joins matches → tournaments for surface and tourney_level.
    Orders by tourney_date ASC, then ROUND_ORDER (via explicit CASE), then match_num.

    Returns
    -------
    list of dict-like sqlite3.Row objects with keys:
        winner_id, loser_id, surface, tourney_date, round, retirement_flag,
        tourney_level, tourney_id, match_num
    """
    sql = """
        SELECT
            m.tourney_id,
            m.match_num,
            m.tour,
            m.winner_id,
            m.loser_id,
            m.round,
            m.tourney_date,
            m.retirement_flag,
            t.surface,
            t.tourney_level
        FROM matches m
        JOIN tournaments t
          ON m.tourney_id = t.tourney_id AND m.tour = t.tour
        WHERE m.match_type IN ('completed', 'retirement')
          AND m.winner_id IS NOT NULL
          AND m.loser_id IS NOT NULL
        ORDER BY
            m.tourney_date ASC,
            CASE m.round
                WHEN 'ER'   THEN 0
                WHEN 'R128' THEN 1
                WHEN 'R64'  THEN 2
                WHEN 'R32'  THEN 3
                WHEN 'R16'  THEN 4
                WHEN 'QF'   THEN 5
                WHEN 'RR'   THEN 5
                WHEN 'BR'   THEN 5
                WHEN 'SF'   THEN 6
                WHEN 'F'    THEN 7
                ELSE 4
            END ASC,
            m.match_num ASC
    """
    return conn.execute(sql).fetchall()


def _group_by_week(matches: list) -> dict:
    """
    Group matches by ISO week.

    Parameters
    ----------
    matches : list
        Ordered list of match rows from _load_matches_ordered.

    Returns
    -------
    dict mapping (iso_year, iso_week) -> list of match rows, sorted by week.
    """
    weeks: dict = {}
    for match in matches:
        key = _get_iso_week(match["tourney_date"])
        if key not in weeks:
            weeks[key] = []
        weeks[key].append(match)
    return weeks


def _seed_players(conn, player_store: dict) -> None:
    """
    Initialize Glicko-2 Player objects for all players in the rankings table.

    Uses the earliest available ranking date for each player to seed their
    initial rating via seed_rating_from_rank. Creates Player objects for all
    four surface tracks.

    Modifies player_store in-place:
        player_store[player_id][surface] = Player(...)
        player_store[player_id]["_last_played"] = {surface: None, ...}
        player_store[player_id]["_matches_played"] = {surface: 0, ...}
    """
    rows = conn.execute(
        """SELECT player_id, ranking
           FROM rankings
           WHERE (player_id, ranking_date) IN (
               SELECT player_id, MIN(ranking_date) FROM rankings GROUP BY player_id
           )"""
    ).fetchall()

    for row in rows:
        pid = row["player_id"]
        rank = row["ranking"]
        initial_rating = seed_rating_from_rank(rank)
        _ensure_player(player_store, pid, initial_rating=initial_rating)


def _ensure_player(
    player_store: dict,
    player_id: int,
    initial_rating: float = DEFAULT_RATING,
) -> None:
    """
    Ensure player_store has an entry for player_id with all four surface tracks.
    Does nothing if already initialized.
    """
    if player_id in player_store:
        return

    player_store[player_id] = {}
    for surface in SURFACES:
        player_store[player_id][surface] = Player(
            rating=initial_rating,
            rd=DEFAULT_RD,
            vol=DEFAULT_VOL,
        )
    player_store[player_id]["_last_played"] = {s: None for s in SURFACES}
    player_store[player_id]["_matches_played"] = {s: 0 for s in SURFACES}


def _freeze_ratings(player_store: dict) -> dict:
    """
    Snapshot all current ratings/RDs/volatilities for use as frozen opponent stats.

    Returns
    -------
    dict mapping player_id -> {surface: (rating, rd, vol)}
    """
    frozen = {}
    for pid, data in player_store.items():
        frozen[pid] = {}
        for surface in SURFACES:
            p = data[surface]
            frozen[pid][surface] = (p.getRating(), p.getRd(), p.vol)
    return frozen


def _effective_outcome(
    base_outcome: float,
    tourney_level: str,
    retirement_flag: int,
) -> float:
    """
    Compute the effective outcome value for Glicko-2 update_player.

    Tournament weighting shrinks the outcome toward 0.5 for lower-tier events.
    Retirement further halves the deviation from 0.5.

    Formula:
        tw = TOURNEY_WEIGHT[tourney_level]
        outcome = base_outcome * tw + 0.5 * (1 - tw)
        if retirement:
            outcome = 0.5 + (outcome - 0.5) * RETIREMENT_MULT

    Parameters
    ----------
    base_outcome : float
        1.0 for win, 0.0 for loss.
    tourney_level : str
        Tournament level code (G/M/A/F/D/C).
    retirement_flag : int
        1 if match ended in retirement.

    Returns
    -------
    float
        Effective outcome in (0.0, 1.0).
    """
    tw = TOURNEY_WEIGHT.get(tourney_level, _DEFAULT_TOURNEY_WEIGHT)
    outcome = base_outcome * tw + 0.5 * (1.0 - tw)

    if retirement_flag:
        # Reduce deviation from 0.5 by retirement multiplier
        outcome = 0.5 + (outcome - 0.5) * RETIREMENT_MULT

    return outcome


def _process_week(
    week_matches: list,
    player_store: dict,
    frozen: dict,
    as_of_date: str,
) -> None:
    """
    Process all matches in one ISO week and update player_store in-place.

    Uses frozen opponent ratings to prevent mid-week contamination.
    After match updates, applies did_not_compete to inactive players and
    decay for those exceeding surface-specific inactivity thresholds.

    Parameters
    ----------
    week_matches : list
        All match rows for this ISO week.
    player_store : dict
        Mutable player store (Player objects + metadata).
    frozen : dict
        Frozen rating snapshot at week start.
    as_of_date : str
        ISO date string for this week's snapshot (end of week Sunday).
    """
    # Accumulate outcomes per (player_id, surface)
    # outcomes[pid][surface] = (rating_list, rd_list, outcome_list)
    outcomes: dict = {}

    def _add_outcome(pid: int, surface: str, opp_rating: float, opp_rd: float, outcome: float):
        if pid not in outcomes:
            outcomes[pid] = {s: ([], [], []) for s in SURFACES}
        outcomes[pid][surface][0].append(opp_rating)
        outcomes[pid][surface][1].append(opp_rd)
        outcomes[pid][surface][2].append(outcome)

    active_this_week: set = set()  # (player_id, surface) pairs that competed

    for match in week_matches:
        winner_id = match["winner_id"]
        loser_id = match["loser_id"]
        surface = match["surface"] or "Hard"
        # Map discontinued surfaces to nearest equivalent
        if surface not in ("Hard", "Clay", "Grass"):
            surface = "Hard"  # Carpet (pre-2009) maps to Hard
        tourney_level = match["tourney_level"] or "A"
        retirement_flag = match["retirement_flag"] or 0

        # Ensure both players are in the store
        _ensure_player(player_store, winner_id)
        _ensure_player(player_store, loser_id)

        # Get frozen opponent ratings
        # Fall back to current store if player not yet in frozen snapshot
        if winner_id in frozen:
            loser_frozen_r, loser_frozen_rd, _ = frozen[loser_id].get(
                surface, (DEFAULT_RATING, DEFAULT_RD, DEFAULT_VOL)
            ) if loser_id in frozen else (DEFAULT_RATING, DEFAULT_RD, DEFAULT_VOL)
            winner_frozen_r, winner_frozen_rd, _ = frozen[winner_id].get(
                surface, (DEFAULT_RATING, DEFAULT_RD, DEFAULT_VOL)
            )
        else:
            winner_frozen_r = player_store[winner_id][surface].getRating()
            winner_frozen_rd = player_store[winner_id][surface].getRd()
            loser_frozen_r = player_store.get(loser_id, {}).get(surface, Player()).getRating() \
                if loser_id in player_store else DEFAULT_RATING
            loser_frozen_rd = player_store.get(loser_id, {}).get(surface, Player()).getRd() \
                if loser_id in player_store else DEFAULT_RD

        # Correctly get frozen loser stats
        if loser_id in frozen:
            loser_frozen_r, loser_frozen_rd, _ = frozen[loser_id].get(
                surface, (DEFAULT_RATING, DEFAULT_RD, DEFAULT_VOL)
            )
        else:
            loser_frozen_r, loser_frozen_rd = DEFAULT_RATING, DEFAULT_RD

        if winner_id in frozen:
            winner_frozen_r, winner_frozen_rd, _ = frozen[winner_id].get(
                surface, (DEFAULT_RATING, DEFAULT_RD, DEFAULT_VOL)
            )
        else:
            winner_frozen_r, winner_frozen_rd = DEFAULT_RATING, DEFAULT_RD

        win_outcome = _effective_outcome(1.0, tourney_level, retirement_flag)
        loss_outcome = _effective_outcome(0.0, tourney_level, retirement_flag)

        # Accumulate for surface track
        _add_outcome(winner_id, surface, loser_frozen_r, loser_frozen_rd, win_outcome)
        _add_outcome(loser_id, surface, winner_frozen_r, winner_frozen_rd, loss_outcome)

        # Also accumulate for Overall track
        _add_outcome(winner_id, "Overall", loser_frozen_r, loser_frozen_rd, win_outcome)
        _add_outcome(loser_id, "Overall", winner_frozen_r, winner_frozen_rd, loss_outcome)

        # Track active players/surfaces
        active_this_week.add((winner_id, surface))
        active_this_week.add((loser_id, surface))
        active_this_week.add((winner_id, "Overall"))
        active_this_week.add((loser_id, "Overall"))

        # Update last_played and matches_played
        for pid in [winner_id, loser_id]:
            player_store[pid]["_last_played"][surface] = as_of_date
            player_store[pid]["_last_played"]["Overall"] = as_of_date
            player_store[pid]["_matches_played"][surface] += 1
            player_store[pid]["_matches_played"]["Overall"] += 1

    # Apply Glicko-2 updates using frozen opponent ratings
    for pid, surface_outcomes in outcomes.items():
        for surface, (r_list, rd_list, o_list) in surface_outcomes.items():
            if r_list:  # only update if there were matches
                player_store[pid][surface].update_player(r_list, rd_list, o_list)

    # Apply did_not_compete to players who were not active this week
    # Only for surface tracks they have previously played on
    for pid, data in player_store.items():
        for surface in SURFACES:
            if (pid, surface) not in active_this_week:
                # Only call did_not_compete if they have a history on this surface
                if data["_matches_played"].get(surface, 0) > 0:
                    data[surface].did_not_compete()

    # Apply inactivity decay for players exceeding surface-specific thresholds
    for pid, data in player_store.items():
        for surface in SURFACES:
            last_played = data["_last_played"].get(surface)
            if last_played is None:
                continue
            # Calculate days since last played on this surface
            last_date = date.fromisoformat(last_played)
            as_of = date.fromisoformat(as_of_date)
            days_inactive = (as_of - last_date).days
            if days_inactive > 0:
                current_rating = data[surface].getRating()
                decayed = apply_decay_if_needed(current_rating, surface, days_inactive)
                if decayed != current_rating:
                    # Directly update the internal rating (glicko2 Player attribute)
                    data[surface].rating = decayed


def _snapshot_to_db(conn, player_store: dict, as_of_date: str) -> int:
    """
    Write one player_elo row per (player_id, surface) into the database.

    Uses INSERT OR REPLACE to handle re-runs idempotently.

    Parameters
    ----------
    conn : sqlite3.Connection
    player_store : dict
    as_of_date : str
        ISO date string "YYYY-MM-DD" for this snapshot.

    Returns
    -------
    int
        Number of rows written.
    """
    count = 0
    for pid, data in player_store.items():
        for surface in SURFACES:
            p = data[surface]
            matches_played = data["_matches_played"].get(surface, 0)
            last_played = data["_last_played"].get(surface)
            conn.execute(
                """INSERT OR REPLACE INTO player_elo
                   (player_id, tour, surface, as_of_date, elo_rating, rd, volatility,
                    matches_played, last_played_date)
                   VALUES (?, 'ATP', ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pid, surface, as_of_date,
                    p.getRating(), p.getRd(), p.vol,
                    matches_played, last_played,
                ),
            )
            count += 1
    conn.commit()
    return count


def compute_all_ratings(conn) -> dict:
    """
    Compute Glicko-2 ratings for all players across all matches.

    Main entry point for the rating engine. Processes matches in strict
    chronological weekly batches with frozen opponent ratings.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection with matches, tournaments, and rankings tables.

    Returns
    -------
    dict
        Summary with keys: total_weeks, total_players, total_snapshots.
    """
    # Load and order all matches
    matches = _load_matches_ordered(conn)
    if not matches:
        return {"total_weeks": 0, "total_players": 0, "total_snapshots": 0}

    # Group by ISO week
    weeks = _group_by_week(matches)

    # Initialize player store and seed from rankings
    player_store: dict = {}
    _seed_players(conn, player_store)

    total_snapshots = 0

    # Process weeks in chronological order
    sorted_weeks = sorted(weeks.keys())
    for week_key in tqdm(sorted_weeks, desc="Rating weeks", unit="wk"):
        iso_year, iso_week = week_key
        week_matches = weeks[week_key]
        as_of_date = _get_week_end_date(iso_year, iso_week)

        # Freeze ratings at week start
        frozen = _freeze_ratings(player_store)

        # Process this week's matches
        _process_week(week_matches, player_store, frozen, as_of_date)

        # Snapshot to DB
        snap_count = _snapshot_to_db(conn, player_store, as_of_date)
        total_snapshots += snap_count

        logger.debug("Week %d-%02d: %d matches, %d players", iso_year, iso_week,
                     len(week_matches), len(player_store))

    return {
        "total_weeks": len(weeks),
        "total_players": len(player_store),
        "total_snapshots": total_snapshots,
    }
