"""
Signals endpoints — persisted prediction signals with status tracking.

Routes:
    GET   /api/v1/signals                  — Upsert signals from predictions, return filtered list.
    PATCH /api/v1/signals/{signal_id}/status — Update signal status (seen/acted-on).

Signals are upserted from the predictions table on each GET call using INSERT OR IGNORE.
Stale signals (tourney past) are automatically expired.
"""

from __future__ import annotations

import asyncio
import logging

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from typing import Optional

from src.api.schemas import SignalRecord, SignalsResponse, SignalStatusUpdate
from src.backtest.kelly import compute_kelly_bet

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])

# Reference bankroll for kelly_stake computation in signals list
_REFERENCE_BANKROLL = 1000.0


# ---------------------------------------------------------------------------
# GET /signals
# ---------------------------------------------------------------------------

@router.get("", response_model=SignalsResponse)
async def get_signals(
    request: Request,
    min_ev: Optional[float] = None,
    surface: Optional[str] = None,
    status: Optional[str] = None,
) -> SignalsResponse:
    """
    Upsert signals from predictions table, expire stale ones, return filtered list.

    Signals are joined with predictions to surface calibrated_prob, ev_value, etc.
    kelly_stake is computed using a $1,000 reference bankroll.
    """
    db_path: str = request.app.state.db_path

    def _sync_fetch() -> list:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            # 1. Upsert new signals from predictions where ev_value > 0
            conn.execute("""
                INSERT OR IGNORE INTO signals
                    (tourney_id, match_num, tour, player_id, model_version,
                     status, created_at, updated_at)
                SELECT
                    tourney_id, match_num, tour, player_id, model_version,
                    'new', datetime('now'), datetime('now')
                FROM predictions
                WHERE ev_value IS NOT NULL AND ev_value > 0
            """)

            # 2. Expire stale signals (tourney date in the past)
            conn.execute("""
                UPDATE signals
                SET status = 'expired', updated_at = datetime('now')
                WHERE status != 'expired'
                  AND tourney_id IN (
                      SELECT tourney_id FROM tournaments WHERE tourney_date < date('now')
                  )
            """)
            conn.commit()

            # 3. Compute CSI tercile bounds in Python (SQLite lacks PERCENTILE_CONT)
            csi_bounds_rows = conn.execute(
                "SELECT csi_value FROM court_speed_index ORDER BY csi_value"
            ).fetchall()
            csi_vals = [float(r[0]) for r in csi_bounds_rows]
            p33 = float(np.percentile(csi_vals, 33.3)) if csi_vals else 0.33
            p67 = float(np.percentile(csi_vals, 66.7)) if csi_vals else 0.67

            # 4. Join signals with predictions and court_speed_index
            query = """
                SELECT
                    s.id, s.tourney_id, s.match_num, s.tour, s.player_id,
                    s.model_version, s.status, s.created_at,
                    p.calibrated_prob, p.ev_value, p.edge, p.decimal_odds,
                    p.predicted_at,
                    csi.csi_value AS court_speed_index
                FROM signals s
                JOIN predictions p
                  ON s.tourney_id = p.tourney_id
                 AND s.match_num = p.match_num
                 AND s.tour = p.tour
                 AND s.player_id = p.player_id
                 AND s.model_version = p.model_version
                LEFT JOIN court_speed_index csi
                  ON s.tourney_id = csi.tourney_id
                 AND csi.tour = s.tour
                WHERE 1=1
            """
            params = []
            if status is not None:
                query += " AND s.status = ?"
                params.append(status)
            query += " ORDER BY s.created_at DESC"

            rows = conn.execute(query, params).fetchall()

            results = []
            for r in rows:
                ev = r["ev_value"]
                if min_ev is not None and (ev is None or ev < min_ev):
                    continue

                # Compute kelly_stake against $1,000 reference bankroll
                kelly_stake = None
                if r["calibrated_prob"] is not None and r["decimal_odds"] is not None:
                    try:
                        kelly_stake = compute_kelly_bet(
                            prob=r["calibrated_prob"],
                            decimal_odds=r["decimal_odds"],
                            bankroll=_REFERENCE_BANKROLL,
                        )
                    except Exception:
                        kelly_stake = None

                # Compute court speed tier from CSI value
                csi_val = r["court_speed_index"]
                tier = None
                if csi_val is not None:
                    if csi_val >= p67:
                        tier = "Fast"
                    elif csi_val <= p33:
                        tier = "Slow"
                    else:
                        tier = "Medium"

                results.append({
                    "id": r["id"],
                    "tourney_id": r["tourney_id"],
                    "match_num": r["match_num"],
                    "tour": r["tour"],
                    "player_id": r["player_id"],
                    "model_version": r["model_version"],
                    "status": r["status"],
                    "calibrated_prob": r["calibrated_prob"],
                    "ev_value": r["ev_value"],
                    "edge": r["edge"],
                    "decimal_odds": r["decimal_odds"],
                    "kelly_stake": kelly_stake,
                    "confidence": None,  # multi-model confidence reserved for future
                    "sharpe": None,
                    "predicted_at": r["predicted_at"],
                    "created_at": r["created_at"],
                    "court_speed_index": csi_val,
                    "court_speed_tier": tier,
                })

            return results

        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _sync_fetch)
    return SignalsResponse(data=[SignalRecord(**r) for r in data])


# ---------------------------------------------------------------------------
# PATCH /signals/{signal_id}/status
# ---------------------------------------------------------------------------

@router.patch("/{signal_id}/status", response_model=SignalRecord)
async def update_signal_status(
    signal_id: int,
    body: SignalStatusUpdate,
    request: Request,
) -> SignalRecord:
    """Update signal status to 'seen' or 'acted-on'."""
    valid_statuses = {"new", "seen", "acted-on", "expired"}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{body.status}'. Must be one of: {sorted(valid_statuses)}",
        )

    db_path: str = request.app.state.db_path

    def _sync_update() -> dict:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT id FROM signals WHERE id = ?", (signal_id,)
            ).fetchone()
            if row is None:
                return None

            conn.execute(
                "UPDATE signals SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (body.status, signal_id),
            )
            conn.commit()

            # Return updated signal joined with predictions
            updated = conn.execute("""
                SELECT
                    s.id, s.tourney_id, s.match_num, s.tour, s.player_id,
                    s.model_version, s.status, s.created_at,
                    p.calibrated_prob, p.ev_value, p.edge, p.decimal_odds,
                    p.predicted_at
                FROM signals s
                JOIN predictions p
                  ON s.tourney_id = p.tourney_id
                 AND s.match_num = p.match_num
                 AND s.tour = p.tour
                 AND s.player_id = p.player_id
                 AND s.model_version = p.model_version
                WHERE s.id = ?
            """, (signal_id,)).fetchone()

            if updated is None:
                # Signal updated but no matching prediction — return minimal record
                sig = conn.execute(
                    "SELECT * FROM signals WHERE id = ?", (signal_id,)
                ).fetchone()
                return {
                    "id": sig["id"],
                    "tourney_id": sig["tourney_id"],
                    "match_num": sig["match_num"],
                    "tour": sig["tour"],
                    "player_id": sig["player_id"],
                    "model_version": sig["model_version"],
                    "status": sig["status"],
                    "created_at": sig["created_at"],
                }

            kelly_stake = None
            if updated["calibrated_prob"] is not None and updated["decimal_odds"] is not None:
                try:
                    kelly_stake = compute_kelly_bet(
                        prob=updated["calibrated_prob"],
                        decimal_odds=updated["decimal_odds"],
                        bankroll=_REFERENCE_BANKROLL,
                    )
                except Exception:
                    kelly_stake = None

            return {
                "id": updated["id"],
                "tourney_id": updated["tourney_id"],
                "match_num": updated["match_num"],
                "tour": updated["tour"],
                "player_id": updated["player_id"],
                "model_version": updated["model_version"],
                "status": updated["status"],
                "calibrated_prob": updated["calibrated_prob"],
                "ev_value": updated["ev_value"],
                "edge": updated["edge"],
                "decimal_odds": updated["decimal_odds"],
                "kelly_stake": kelly_stake,
                "predicted_at": updated["predicted_at"],
                "created_at": updated["created_at"],
            }

        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _sync_update)

    if result is None:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    return SignalRecord(**result)
