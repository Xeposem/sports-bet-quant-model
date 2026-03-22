"""
Paper trading endpoints — session management, bet placement, and resolution.

Routes:
    GET    /api/v1/paper/session           — Return active paper trading session.
    POST   /api/v1/paper/session           — Create new session (deactivates existing).
    DELETE /api/v1/paper/session           — Deactivate current session.
    POST   /api/v1/paper/bets              — Place a paper bet from a signal.
    GET    /api/v1/paper/bets              — Return all bets for active session.
    PATCH  /api/v1/paper/bets/{bet_id}/resolve — Resolve a bet with outcome.
    GET    /api/v1/paper/equity            — Return equity curve for active session.

Paper bets use compute_kelly_bet for sizing. Resolution uses apply_bet_result P&L logic.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response

from src.api.schemas import (
    PaperBetPlace,
    PaperBetResolve,
    PaperBetRow,
    PaperBetsResponse,
    PaperEquityPoint,
    PaperEquityResponse,
    PaperSessionCreate,
    PaperSessionResponse,
)
from src.backtest.kelly import compute_kelly_bet

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/paper", tags=["paper"])


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# GET /paper/session
# ---------------------------------------------------------------------------

@router.get("/session", response_model=PaperSessionResponse)
async def get_paper_session(request: Request) -> PaperSessionResponse:
    """Return the active paper trading session with aggregate stats."""
    db_path: str = request.app.state.db_path

    def _sync_fetch() -> Optional[dict]:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            sess = conn.execute(
                "SELECT * FROM paper_sessions WHERE active = 1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if sess is None:
                return None

            session_id = sess["id"]
            bets = conn.execute(
                "SELECT outcome, pnl, kelly_stake FROM paper_bets WHERE session_id = ?",
                (session_id,),
            ).fetchall()

            total_bets = len(bets)
            resolved = [b for b in bets if b["outcome"] is not None]
            resolved_bets = len(resolved)
            wins = sum(1 for b in resolved if b["outcome"] == 1)
            win_rate = wins / resolved_bets if resolved_bets > 0 else None
            total_pnl = sum(b["pnl"] for b in resolved if b["pnl"] is not None)

            return {
                "id": session_id,
                "initial_bankroll": sess["initial_bankroll"],
                "current_bankroll": sess["current_bankroll"],
                "kelly_fraction": sess["kelly_fraction"],
                "ev_threshold": sess["ev_threshold"],
                "started_at": sess["started_at"],
                "active": sess["active"],
                "total_bets": total_bets,
                "resolved_bets": resolved_bets,
                "win_rate": win_rate,
                "total_pnl": total_pnl,
            }
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _sync_fetch)

    if data is None:
        raise HTTPException(status_code=404, detail="No active paper trading session.")

    return PaperSessionResponse(**data)


# ---------------------------------------------------------------------------
# POST /paper/session
# ---------------------------------------------------------------------------

@router.post("/session", response_model=PaperSessionResponse, status_code=201)
async def create_paper_session(
    body: PaperSessionCreate, request: Request
) -> PaperSessionResponse:
    """Create a new paper trading session, deactivating any existing active session."""
    db_path: str = request.app.state.db_path

    def _sync_create() -> dict:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Deactivate existing active sessions
            conn.execute(
                "UPDATE paper_sessions SET active = 0, reset_at = ? WHERE active = 1",
                (_now(),),
            )
            # Create new active session
            started_at = _now()
            cursor = conn.execute(
                """
                INSERT INTO paper_sessions
                    (tour, initial_bankroll, current_bankroll, kelly_fraction,
                     ev_threshold, started_at, active)
                VALUES ('ATP', ?, ?, ?, ?, ?, 1)
                """,
                (
                    body.initial_bankroll,
                    body.initial_bankroll,
                    body.kelly_fraction,
                    body.ev_threshold,
                    started_at,
                ),
            )
            conn.commit()
            session_id = cursor.lastrowid
            return {
                "id": session_id,
                "initial_bankroll": body.initial_bankroll,
                "current_bankroll": body.initial_bankroll,
                "kelly_fraction": body.kelly_fraction,
                "ev_threshold": body.ev_threshold,
                "started_at": started_at,
                "active": 1,
                "total_bets": 0,
                "resolved_bets": 0,
                "win_rate": None,
                "total_pnl": 0.0,
            }
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _sync_create)
    return PaperSessionResponse(**data)


# ---------------------------------------------------------------------------
# DELETE /paper/session
# ---------------------------------------------------------------------------

@router.delete("/session", status_code=204)
async def delete_paper_session(request: Request) -> Response:
    """Deactivate the current active paper trading session."""
    db_path: str = request.app.state.db_path

    def _sync_delete() -> int:
        import sqlite3
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.execute(
                "UPDATE paper_sessions SET active = 0, reset_at = ? WHERE active = 1",
                (_now(),),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    rows_affected = await loop.run_in_executor(None, _sync_delete)

    if rows_affected == 0:
        raise HTTPException(status_code=404, detail="No active paper trading session.")

    return Response(status_code=204)


# ---------------------------------------------------------------------------
# POST /paper/bets
# ---------------------------------------------------------------------------

@router.post("/bets", response_model=PaperBetRow, status_code=201)
async def place_paper_bet(body: PaperBetPlace, request: Request) -> PaperBetRow:
    """Place a paper bet from a signal using Kelly sizing."""
    db_path: str = request.app.state.db_path

    def _sync_place() -> dict:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Get active session
            sess = conn.execute(
                "SELECT * FROM paper_sessions WHERE active = 1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if sess is None:
                raise HTTPException(status_code=404, detail="No active paper trading session.")

            # Get signal
            sig = conn.execute(
                "SELECT * FROM signals WHERE id = ?", (body.signal_id,)
            ).fetchone()
            if sig is None:
                raise HTTPException(status_code=404, detail=f"Signal {body.signal_id} not found.")

            # Get prediction data
            pred = conn.execute(
                """
                SELECT calibrated_prob, decimal_odds, ev_value
                FROM predictions
                WHERE tourney_id = ? AND match_num = ? AND tour = ?
                  AND player_id = ? AND model_version = ?
                """,
                (sig["tourney_id"], sig["match_num"], sig["tour"],
                 sig["player_id"], sig["model_version"]),
            ).fetchone()
            if pred is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"No prediction found for signal {body.signal_id}.",
                )

            calibrated_prob = pred["calibrated_prob"]
            decimal_odds = pred["decimal_odds"]
            ev_value = pred["ev_value"]
            current_bankroll = sess["current_bankroll"]

            # Compute Kelly stake
            kelly_stake = compute_kelly_bet(
                prob=calibrated_prob,
                decimal_odds=decimal_odds,
                bankroll=current_bankroll,
                kelly_fraction=sess["kelly_fraction"],
            )

            placed_at = _now()
            cursor = conn.execute(
                """
                INSERT INTO paper_bets
                    (session_id, tour, tourney_id, match_num, player_id, model_version,
                     calibrated_prob, decimal_odds, ev_value, kelly_stake, bankroll_before,
                     placed_at)
                VALUES (?, 'ATP', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sess["id"],
                    sig["tourney_id"],
                    sig["match_num"],
                    sig["player_id"],
                    sig["model_version"],
                    calibrated_prob,
                    decimal_odds,
                    ev_value,
                    kelly_stake,
                    current_bankroll,
                    placed_at,
                ),
            )
            conn.commit()
            bet_id = cursor.lastrowid

            return {
                "id": bet_id,
                "session_id": sess["id"],
                "tourney_id": sig["tourney_id"],
                "match_num": sig["match_num"],
                "player_id": sig["player_id"],
                "model_version": sig["model_version"],
                "calibrated_prob": calibrated_prob,
                "decimal_odds": decimal_odds,
                "ev_value": ev_value,
                "kelly_stake": kelly_stake,
                "bankroll_before": current_bankroll,
                "bankroll_after": None,
                "outcome": None,
                "pnl": None,
                "placed_at": placed_at,
                "resolved_at": None,
                "result_source": None,
            }
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _sync_place)
    return PaperBetRow(**data)


# ---------------------------------------------------------------------------
# GET /paper/bets
# ---------------------------------------------------------------------------

@router.get("/bets", response_model=PaperBetsResponse)
async def get_paper_bets(request: Request) -> PaperBetsResponse:
    """Return all bets for the active paper trading session, most recent first."""
    db_path: str = request.app.state.db_path

    def _sync_fetch() -> list:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            sess = conn.execute(
                "SELECT id FROM paper_sessions WHERE active = 1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if sess is None:
                return []

            rows = conn.execute(
                "SELECT * FROM paper_bets WHERE session_id = ? ORDER BY placed_at DESC",
                (sess["id"],),
            ).fetchall()

            return [dict(r) for r in rows]
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _sync_fetch)
    return PaperBetsResponse(data=[PaperBetRow(**r) for r in data])


# ---------------------------------------------------------------------------
# PATCH /paper/bets/{bet_id}/resolve
# ---------------------------------------------------------------------------

@router.patch("/bets/{bet_id}/resolve", response_model=PaperBetRow)
async def resolve_paper_bet(
    bet_id: int, body: PaperBetResolve, request: Request
) -> PaperBetRow:
    """Resolve a paper bet with the actual match outcome. Updates session bankroll."""
    if body.outcome not in (0, 1):
        raise HTTPException(status_code=422, detail="outcome must be 0 (lost) or 1 (won)")

    db_path: str = request.app.state.db_path

    def _sync_resolve() -> dict:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            bet = conn.execute(
                "SELECT * FROM paper_bets WHERE id = ?", (bet_id,)
            ).fetchone()
            if bet is None:
                raise HTTPException(status_code=404, detail=f"Bet {bet_id} not found.")

            # Compute P&L
            kelly_stake = bet["kelly_stake"]
            decimal_odds = bet["decimal_odds"]
            bankroll_before = bet["bankroll_before"]

            if body.outcome == 1:
                pnl = kelly_stake * (decimal_odds - 1.0)
            else:
                pnl = -kelly_stake

            bankroll_after = bankroll_before + pnl
            resolved_at = _now()

            conn.execute(
                """
                UPDATE paper_bets
                SET outcome = ?, pnl = ?, bankroll_after = ?, resolved_at = ?
                WHERE id = ?
                """,
                (body.outcome, pnl, bankroll_after, resolved_at, bet_id),
            )

            # Update session current_bankroll
            conn.execute(
                "UPDATE paper_sessions SET current_bankroll = ? WHERE id = ?",
                (bankroll_after, bet["session_id"]),
            )
            conn.commit()

            updated = conn.execute(
                "SELECT * FROM paper_bets WHERE id = ?", (bet_id,)
            ).fetchone()
            return dict(updated)

        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _sync_resolve)
    return PaperBetRow(**data)


# ---------------------------------------------------------------------------
# GET /paper/equity
# ---------------------------------------------------------------------------

@router.get("/equity", response_model=PaperEquityResponse)
async def get_paper_equity(request: Request) -> PaperEquityResponse:
    """Return equity curve for the active paper trading session."""
    db_path: str = request.app.state.db_path

    def _sync_equity() -> dict:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            sess = conn.execute(
                "SELECT * FROM paper_sessions WHERE active = 1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if sess is None:
                return {
                    "initial": 0.0,
                    "current": 0.0,
                    "total_pnl": 0.0,
                    "win_rate": None,
                    "curve": [],
                }

            # Resolved bets ordered by placed_at for equity curve
            resolved = conn.execute(
                """
                SELECT placed_at, bankroll_after, outcome, pnl
                FROM paper_bets
                WHERE session_id = ? AND bankroll_after IS NOT NULL
                ORDER BY placed_at ASC
                """,
                (sess["id"],),
            ).fetchall()

            curve = []
            for r in resolved:
                # Use date portion of placed_at as curve x-axis
                date_part = r["placed_at"][:10] if r["placed_at"] else "unknown"
                curve.append({
                    "date": date_part,
                    "bankroll": r["bankroll_after"],
                })

            total_pnl = sum(r["pnl"] for r in resolved if r["pnl"] is not None)
            wins = sum(1 for r in resolved if r["outcome"] == 1)
            total_resolved = len(resolved)
            win_rate = wins / total_resolved if total_resolved > 0 else None

            return {
                "initial": sess["initial_bankroll"],
                "current": sess["current_bankroll"],
                "total_pnl": total_pnl,
                "win_rate": win_rate,
                "curve": curve,
            }
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _sync_equity)

    curve = [PaperEquityPoint(**p) for p in data["curve"]]
    return PaperEquityResponse(
        initial=data["initial"],
        current=data["current"],
        total_pnl=data["total_pnl"],
        win_rate=data["win_rate"],
        curve=curve,
    )
