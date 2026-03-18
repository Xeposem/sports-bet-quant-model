"""
GET /api/v1/bankroll — returns the equity curve and summary statistics.

Queries backtest_results ordered by tourney_date, id to reconstruct the bankroll
time-series. Computes initial, current, peak, and max_drawdown from the curve.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from sqlalchemy import text

from src.api.deps import DbDep
from src.api.schemas import BankrollPoint, BankrollResponse

router = APIRouter(prefix="/bankroll", tags=["bankroll"])


@router.get("", response_model=BankrollResponse)
async def get_bankroll(
    db: DbDep,
    model: str = "logistic_v1",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> BankrollResponse:
    """Return bankroll curve and summary statistics for the specified model."""
    conditions: List[str] = [
        "kelly_bet > 0",
        "model_version = :model",
    ]
    params: dict = {"model": model}

    if date_from is not None:
        conditions.append("tourney_date >= :date_from")
        params["date_from"] = date_from

    if date_to is not None:
        conditions.append("tourney_date <= :date_to")
        params["date_to"] = date_to

    where = " AND ".join(conditions)

    sql = text(
        f"""
        SELECT tourney_date, bankroll_before, bankroll_after
        FROM backtest_results
        WHERE {where}
        ORDER BY tourney_date, id
        """
    )

    rows = (await db.execute(sql, params)).mappings().all()

    if not rows:
        return BankrollResponse(
            initial=0.0,
            current=0.0,
            peak=0.0,
            max_drawdown=0.0,
            curve=[],
        )

    initial = rows[0]["bankroll_before"]
    current = rows[-1]["bankroll_after"]

    curve: List[BankrollPoint] = []
    peak = initial
    max_drawdown = 0.0

    for row in rows:
        ba = row["bankroll_after"]
        if ba > peak:
            peak = ba
        drawdown = (peak - ba) / peak if peak > 0 else 0.0
        if drawdown > max_drawdown:
            max_drawdown = drawdown
        curve.append(BankrollPoint(date=row["tourney_date"], bankroll=ba))

    return BankrollResponse(
        initial=initial,
        current=current,
        peak=peak,
        max_drawdown=max_drawdown,
        curve=curve,
    )
