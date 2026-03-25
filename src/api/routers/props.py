"""
Props endpoints — manual prop line entry, real prediction retrieval, and accuracy tracking.

Routes:
    GET  /api/v1/props           — Real prop predictions joined with prop lines (p_hit from PMF).
    GET  /api/v1/props/accuracy  — Prediction accuracy metrics: hit rates, rolling 30d, calibration.
    POST /api/v1/props           — Manual PrizePicks prop line entry with fuzzy player matching.

Valid stat_type values: "aces", "games_won", "double_faults"
Valid direction values: "over", "under"

DB writes use sync sqlite3 connections offloaded via run_in_executor.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, UploadFile, File

from fastapi.responses import Response as FastAPIResponse

from src.api.schemas import (
    PropLineEntry,
    PropLineResponse,
    PropAccuracyBin,
    PropAccuracyResponse,
    PropPredictionRow,
    PropsListResponse,
    PropLineListRow,
    PropLinesListResponse,
    PropScanResponse,
)
from src.props.base import p_over

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/props", tags=["props"])

_VALID_STAT_TYPES = {"aces", "games_won", "double_faults"}
_VALID_DIRECTIONS = {"over", "under"}


# ---------------------------------------------------------------------------
# GET /props/accuracy  — must be registered BEFORE GET /props ("" route)
# so FastAPI does not confuse "/accuracy" as a path param
# ---------------------------------------------------------------------------

@router.get("/accuracy", response_model=PropAccuracyResponse)
async def get_props_accuracy(request: Request) -> PropAccuracyResponse:
    """Return prop prediction accuracy metrics for tracking."""
    db_path: str = request.app.state.db_path

    def _sync_compute() -> dict:
        from src.db.connection import get_connection
        conn = get_connection(db_path)
        try:
            # Get all resolved predictions that have a matching prop_line
            resolved = conn.execute("""
                SELECT p.stat_type, p.actual_value, p.mu, p.pmf_json,
                       p.match_date, pl.line_value, pl.direction
                FROM prop_predictions p
                JOIN prop_lines pl
                  ON p.player_id = pl.player_id
                  AND p.stat_type = pl.stat_type
                  AND p.match_date = pl.match_date
                WHERE p.actual_value IS NOT NULL
                ORDER BY p.match_date
            """).fetchall()

            if not resolved:
                return {
                    "status": "ok",
                    "overall_hit_rate": None,
                    "hit_rate_by_stat": {"aces": None, "games_won": None, "double_faults": None},
                    "total_tracked": 0,
                    "rolling_30d": [],
                    "calibration_bins": [],
                }

            # Compute hits
            hits_total = 0
            hits_by_stat = {"aces": [0, 0], "games_won": [0, 0], "double_faults": [0, 0]}
            predicted_ps = []  # (predicted_p, did_hit, date) for rolling/calibration

            for r in resolved:
                pmf = json.loads(r["pmf_json"])
                p_o = p_over(pmf, r["line_value"])
                p_hit_val = p_o if r["direction"] == "over" else (1.0 - p_o)
                actual_hit = (
                    (r["actual_value"] > r["line_value"])
                    if r["direction"] == "over"
                    else (r["actual_value"] < r["line_value"])
                )
                did_hit = 1 if actual_hit else 0
                hits_total += did_hit
                st = r["stat_type"]
                if st in hits_by_stat:
                    hits_by_stat[st][0] += did_hit
                    hits_by_stat[st][1] += 1
                predicted_ps.append((p_hit_val, did_hit, r["match_date"]))

            total = len(resolved)
            overall_hr = hits_total / total if total > 0 else None
            hr_by_stat = {}
            for st, (h, n) in hits_by_stat.items():
                hr_by_stat[st] = h / n if n > 0 else None

            # Rolling 30d (group by date, compute running 30-day window)
            daily = defaultdict(lambda: [0, 0])
            for p_val, hit, dt in predicted_ps:
                daily[dt][0] += hit
                daily[dt][1] += 1
            dates_sorted = sorted(daily.keys())
            rolling = []
            for i, d in enumerate(dates_sorted):
                window_hits = sum(daily[dd][0] for dd in dates_sorted[max(0, i - 29):i + 1])
                window_total = sum(daily[dd][1] for dd in dates_sorted[max(0, i - 29):i + 1])
                rolling.append({
                    "date": d,
                    "hit_rate": round(window_hits / window_total, 4) if window_total > 0 else 0,
                })

            # Calibration bins (10 bins from 0.0-1.0)
            bins_data = defaultdict(lambda: [0, 0])
            for p_val, hit, _ in predicted_ps:
                bucket = min(int(p_val * 10), 9)
                bins_data[bucket][0] += hit
                bins_data[bucket][1] += 1
            cal_bins = []
            for b in range(10):
                if bins_data[b][1] > 0:
                    cal_bins.append({
                        "predicted_p": (b + 0.5) / 10,
                        "actual_hit_rate": bins_data[b][0] / bins_data[b][1],
                        "n": bins_data[b][1],
                    })

            return {
                "status": "ok",
                "overall_hit_rate": round(overall_hr, 4) if overall_hr is not None else None,
                "hit_rate_by_stat": hr_by_stat,
                "total_tracked": total,
                "rolling_30d": rolling,
                "calibration_bins": cal_bins,
            }
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _sync_compute)
    return PropAccuracyResponse(**data)


# ---------------------------------------------------------------------------
# GET /props  — real predictions with p_hit from PMF
# ---------------------------------------------------------------------------

@router.get("", response_model=PropsListResponse)
async def get_props(request: Request) -> PropsListResponse:
    """Return prop predictions with P(over/under) computed from stored PMF."""
    db_path: str = request.app.state.db_path

    def _sync_fetch() -> list[dict]:
        from src.db.connection import get_connection
        conn = get_connection(db_path)
        try:
            rows = conn.execute("""
                SELECT p.id, p.player_name, p.stat_type, p.match_date,
                       p.mu, p.pmf_json, p.model_version,
                       p.actual_value, p.resolved_at,
                       pl.line_value, pl.direction
                FROM prop_predictions p
                LEFT JOIN prop_lines pl
                  ON p.player_id = pl.player_id
                  AND p.stat_type = pl.stat_type
                  AND p.match_date = pl.match_date
                ORDER BY p.match_date DESC
                LIMIT 200
            """).fetchall()
            result = []
            for r in rows:
                pmf = json.loads(r["pmf_json"])
                p_hit = None
                if r["line_value"] is not None and r["direction"] is not None:
                    p_o = p_over(pmf, r["line_value"])
                    p_hit = p_o if r["direction"] == "over" else (1.0 - p_o)
                result.append({
                    "id": r["id"],
                    "player_name": r["player_name"],
                    "stat_type": r["stat_type"],
                    "match_date": r["match_date"],
                    "mu": r["mu"],
                    "pmf": pmf,
                    "model_version": r["model_version"],
                    "actual_value": r["actual_value"],
                    "resolved_at": r["resolved_at"],
                    "line_value": r["line_value"],
                    "direction": r["direction"],
                    "p_hit": round(p_hit, 4) if p_hit is not None else None,
                })
            return result
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _sync_fetch)
    return PropsListResponse(status="ok", data=data)


# ---------------------------------------------------------------------------
# POST /props/scan  — PrizePicks screenshot OCR scan
# Must be registered BEFORE POST "" to avoid routing conflicts
# ---------------------------------------------------------------------------

@router.post("/scan", response_model=PropScanResponse)
async def scan_prop_screenshot(
    file: UploadFile = File(...),
    request: Request = None,
) -> PropScanResponse:
    """Accept PrizePicks screenshot, extract ATP prop cards via OCR."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="File must be an image (JPEG, PNG, etc.)")

    contents = await file.read()
    db_path: str = request.app.state.db_path

    def _run() -> dict:
        from src.props.scanner import scan_image_bytes
        return scan_image_bytes(contents, db_path)

    try:
        data = await asyncio.to_thread(_run)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scanner error: {exc}")

    if data.get("status") == "tesseract_not_found":
        raise HTTPException(status_code=503, detail="Tesseract OCR not installed on server")

    return PropScanResponse(**data)


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


# ---------------------------------------------------------------------------
# GET /props/lines  — list all prop lines
# ---------------------------------------------------------------------------

@router.get("/lines", response_model=PropLinesListResponse)
async def get_prop_lines(request: Request) -> PropLinesListResponse:
    """Return all manually entered prop lines."""
    db_path: str = request.app.state.db_path

    def _sync_list() -> list:
        from src.db.connection import get_connection
        conn = get_connection(db_path)
        try:
            rows = conn.execute(
                """
                SELECT id, player_name, stat_type, line_value, direction,
                       match_date, bookmaker, entered_at
                FROM prop_lines
                ORDER BY entered_at DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _sync_list)
    return PropLinesListResponse(data=[PropLineListRow(**r) for r in data])


# ---------------------------------------------------------------------------
# DELETE /props/lines/{line_id}  — delete a prop line
# ---------------------------------------------------------------------------

@router.delete("/lines/{line_id}", status_code=204)
async def delete_prop_line(line_id: int, request: Request) -> FastAPIResponse:
    """Delete a prop line by ID."""
    db_path: str = request.app.state.db_path

    def _sync_delete() -> int:
        from src.db.connection import get_connection
        conn = get_connection(db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM prop_lines WHERE id = ?", (line_id,)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    rows_affected = await loop.run_in_executor(None, _sync_delete)

    if rows_affected == 0:
        raise HTTPException(status_code=404, detail=f"Prop line {line_id} not found.")

    return FastAPIResponse(status_code=204)
