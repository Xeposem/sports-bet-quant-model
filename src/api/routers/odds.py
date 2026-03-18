"""
Odds entry endpoints — manual JSON entry and CSV file upload.

Routes:
    POST /api/v1/odds        — Single match odds entry with fuzzy player matching.
    POST /api/v1/odds/upload — CSV file upload via multipart/form-data.

All DB writes use sync sqlite3 connections offloaded via run_in_executor to avoid
blocking the async event loop and to prevent write contention with aiosqlite
(per Phase 5 RESEARCH.md Pitfall 2).

Module-level imports (link_odds_to_matches, upsert_match_odds, import_csv_odds) allow
patching at module scope in tests — same pattern as src.refresh.runner.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, File, Request, UploadFile

from src.api.schemas import OddsEntry, OddsEntryResponse, OddsUploadResponse
from src.db.connection import get_connection
from src.odds.ingester import import_csv_odds, upsert_match_odds
from src.odds.linker import link_odds_to_matches

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/odds", tags=["odds"])


# ---------------------------------------------------------------------------
# POST /odds  —  single match odds entry
# ---------------------------------------------------------------------------

@router.post("", response_model=OddsEntryResponse)
async def post_odds_entry(body: OddsEntry, request: Request) -> OddsEntryResponse:
    """Accept a JSON odds entry, fuzzy-link to a match, and store if linked."""
    db_path: str = request.app.state.db_path

    def _sync_entry() -> OddsEntryResponse:
        conn = get_connection(db_path)
        try:
            odds_row = {
                "match_date": body.match_date,
                "winner_name": body.player_a,
                "loser_name": body.player_b,
                "decimal_odds_winner": body.odds_a,
                "decimal_odds_loser": body.odds_b,
            }
            linked_rows = link_odds_to_matches(conn, [odds_row])
            linked_row = linked_rows[0] if linked_rows else {}

            if linked_row.get("tourney_id") is not None:
                upsert_match_odds(
                    conn,
                    {
                        "tourney_id": linked_row["tourney_id"],
                        "match_num": linked_row["match_num"],
                        "tour": linked_row.get("tour", "ATP"),
                        "bookmaker": body.bookmaker,
                        "decimal_odds_a": body.odds_a,
                        "decimal_odds_b": body.odds_b,
                        "source": "manual",
                    },
                )
                conn.commit()
                return OddsEntryResponse(
                    linked=True,
                    tourney_id=linked_row["tourney_id"],
                    match_num=linked_row["match_num"],
                    message="Odds linked and stored",
                )

            # Not linked — return top candidates near the date
            try:
                center_date = date.fromisoformat(body.match_date)
            except ValueError:
                center_date = date.today()

            start_date = (center_date - timedelta(days=3)).isoformat()
            end_date = (center_date + timedelta(days=3)).isoformat()

            candidate_rows = conn.execute(
                """
                SELECT
                    pw.first_name || ' ' || pw.last_name AS winner_full,
                    pl.first_name || ' ' || pl.last_name AS loser_full
                FROM matches m
                JOIN players pw ON pw.player_id = m.winner_id AND pw.tour = m.tour
                JOIN players pl ON pl.player_id = m.loser_id AND pl.tour = m.tour
                WHERE m.tourney_date BETWEEN ? AND ?
                LIMIT 10
                """,
                (start_date, end_date),
            ).fetchall()

            candidates = []
            for row in candidate_rows[:5]:
                candidates.append(f"{row['winner_full']} vs {row['loser_full']}")

            return OddsEntryResponse(
                linked=False,
                candidates=candidates,
                message="Could not auto-link. Review candidates.",
            )
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_entry)


# ---------------------------------------------------------------------------
# POST /odds/upload  —  CSV file upload
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=OddsUploadResponse)
async def post_odds_upload(
    file: UploadFile = File(...),
    request: Request = None,
) -> OddsUploadResponse:
    """Accept a tennis-data.co.uk CSV file and import odds into the database."""
    db_path: str = request.app.state.db_path

    # Read the uploaded file contents
    contents = await file.read()
    text = contents.decode("utf-8")

    # Write to a temp file because import_csv_odds takes a filepath
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".csv")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(text)

        def _sync_import() -> dict:
            conn = get_connection(db_path)
            try:
                result = import_csv_odds(conn, tmp_path)
                return result
            finally:
                conn.close()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _sync_import)

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # import_csv_odds returns: imported, unlinked, skipped_no_odds
    imported = result.get("imported", 0)
    skipped = result.get("unlinked", 0) + result.get("skipped_no_odds", 0)
    total = imported + skipped

    return OddsUploadResponse(imported=imported, skipped=skipped, total=total)
