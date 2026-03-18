"""
Props endpoints — manual prop line entry and retrieval.

Routes:
    GET  /api/v1/props  — Stub until Phase 8 (returns not_available).
    POST /api/v1/props  — Manual PrizePicks prop line entry with fuzzy player matching.

Valid stat_type values: "aces", "games_won", "double_faults"
Valid direction values: "over", "under"

DB writes use sync sqlite3 connections offloaded via run_in_executor.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from src.api.schemas import PropLineEntry, PropLineResponse, PropsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/props", tags=["props"])

_VALID_STAT_TYPES = {"aces", "games_won", "double_faults"}
_VALID_DIRECTIONS = {"over", "under"}


# ---------------------------------------------------------------------------
# GET /props  — stub until Phase 8
# ---------------------------------------------------------------------------

@router.get("", response_model=PropsResponse)
async def get_props() -> PropsResponse:
    """Return stub response — props analysis implemented in Phase 8."""
    return PropsResponse(status="not_available", data=[])


# ---------------------------------------------------------------------------
# POST /props  — manual prop line entry
# ---------------------------------------------------------------------------

@router.post("", response_model=PropLineResponse, status_code=200)
async def post_prop_line(body: PropLineEntry, request: Request) -> PropLineResponse:
    """Store a manual prop line entry with fuzzy player name resolution."""
    # Validate stat_type and direction before hitting the DB
    if body.stat_type not in _VALID_STAT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid stat_type '{body.stat_type}'. Must be one of: {sorted(_VALID_STAT_TYPES)}",
        )
    if body.direction not in _VALID_DIRECTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid direction '{body.direction}'. Must be one of: {sorted(_VALID_DIRECTIONS)}",
        )

    db_path: str = request.app.state.db_path
    entered_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    def _sync_insert() -> dict:
        from src.db.connection import get_connection
        from src.odds.linker import fuzzy_link_player

        conn = get_connection(db_path)
        try:
            # Attempt fuzzy player name resolution
            player_id: Optional[int] = None
            try:
                player_rows = conn.execute(
                    "SELECT player_id, first_name || ' ' || last_name AS full_name FROM players"
                ).fetchall()
                candidate_names = [r["full_name"] for r in player_rows]
                matched_name = fuzzy_link_player(body.player_name, candidate_names, threshold=85)
                if matched_name is not None:
                    for row in player_rows:
                        if row["full_name"] == matched_name:
                            player_id = row["player_id"]
                            break
            except Exception as exc:
                logger.debug("Player fuzzy match skipped: %s", exc)
                player_id = None

            cursor = conn.execute(
                """
                INSERT INTO prop_lines
                    (tour, player_id, player_name, stat_type, line_value,
                     direction, match_date, bookmaker, entered_at)
                VALUES
                    ('ATP', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    player_id,
                    body.player_name,
                    body.stat_type,
                    body.line_value,
                    body.direction,
                    body.match_date,
                    body.bookmaker,
                    entered_at,
                ),
            )
            conn.commit()
            row_id = cursor.lastrowid
            return {
                "id": row_id,
                "player_name": body.player_name,
                "stat_type": body.stat_type,
                "line_value": body.line_value,
                "direction": body.direction,
                "match_date": body.match_date,
            }
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _sync_insert)
    return PropLineResponse(**result)
