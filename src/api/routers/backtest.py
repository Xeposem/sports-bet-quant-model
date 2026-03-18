"""
Backtest read endpoints.

GET /api/v1/backtest      — aggregate summary stats with ROI breakdowns
GET /api/v1/backtest/bets — paginated individual bet rows
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from sqlalchemy import text

from src.api.deps import DbDep
from src.api.schemas import (
    BacktestBetRow,
    BacktestSummary,
    PaginatedBetsResponse,
)

router = APIRouter(prefix="/backtest", tags=["backtest"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_roi(pnl: Optional[float], stake: Optional[float]) -> float:
    """Return pnl/stake, defaulting to 0.0 on None or zero stake."""
    if not stake:
        return 0.0
    return (pnl or 0.0) / stake


def _breakdown_rows(raw_rows) -> List[Dict[str, Any]]:
    """Convert SQLAlchemy mapping rows to plain dicts for breakdown lists."""
    result = []
    for row in raw_rows:
        d = dict(row)
        kelly_stake = d.get("sum_kelly_bet") or 0.0
        flat_stake = d.get("sum_flat_bet") or 0.0
        d["kelly_roi"] = _safe_roi(d.get("sum_pnl_kelly"), kelly_stake)
        d["flat_roi"] = _safe_roi(d.get("sum_pnl_flat"), flat_stake)
        d["total_pnl_kelly"] = d.get("sum_pnl_kelly") or 0.0
        d["total_pnl_flat"] = d.get("sum_pnl_flat") or 0.0
        # Remove internal aggregate keys
        for k in ("sum_kelly_bet", "sum_flat_bet", "sum_pnl_kelly", "sum_pnl_flat"):
            d.pop(k, None)
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# GET /backtest — summary
# ---------------------------------------------------------------------------

@router.get("", response_model=BacktestSummary)
async def get_backtest_summary(
    db: DbDep,
    model: str = "logistic_v1",
) -> BacktestSummary:
    """Return aggregate backtest statistics with per-dimension ROI breakdowns."""
    params: dict = {"model": model}

    # --- Overall aggregates ---
    overall_sql = text(
        """
        SELECT
            COUNT(*)        AS n_bets,
            SUM(pnl_kelly)  AS sum_pnl_kelly,
            SUM(kelly_bet)  AS sum_kelly_bet,
            SUM(pnl_flat)   AS sum_pnl_flat,
            SUM(flat_bet)   AS sum_flat_bet
        FROM backtest_results
        WHERE kelly_bet > 0
          AND model_version = :model
        """
    )
    overall = (await db.execute(overall_sql, params)).mappings().one()

    n_bets = overall["n_bets"] or 0
    kelly_roi = _safe_roi(overall["sum_pnl_kelly"], overall["sum_kelly_bet"])
    flat_roi = _safe_roi(overall["sum_pnl_flat"], overall["sum_flat_bet"])
    total_pnl_kelly = overall["sum_pnl_kelly"] or 0.0
    total_pnl_flat = overall["sum_pnl_flat"] or 0.0

    # --- by_surface ---
    by_surface_sql = text(
        """
        SELECT
            COALESCE(surface, 'Unknown') AS label,
            COUNT(*)        AS n_bets,
            SUM(pnl_kelly)  AS sum_pnl_kelly,
            SUM(kelly_bet)  AS sum_kelly_bet,
            SUM(pnl_flat)   AS sum_pnl_flat,
            SUM(flat_bet)   AS sum_flat_bet
        FROM backtest_results
        WHERE kelly_bet > 0
          AND model_version = :model
        GROUP BY surface
        ORDER BY label
        """
    )
    by_surface = _breakdown_rows((await db.execute(by_surface_sql, params)).mappings().all())

    # --- by_tourney_level ---
    by_level_sql = text(
        """
        SELECT
            COALESCE(tourney_level, 'Unknown') AS label,
            COUNT(*)        AS n_bets,
            SUM(pnl_kelly)  AS sum_pnl_kelly,
            SUM(kelly_bet)  AS sum_kelly_bet,
            SUM(pnl_flat)   AS sum_pnl_flat,
            SUM(flat_bet)   AS sum_flat_bet
        FROM backtest_results
        WHERE kelly_bet > 0
          AND model_version = :model
        GROUP BY tourney_level
        ORDER BY label
        """
    )
    by_tourney_level = _breakdown_rows(
        (await db.execute(by_level_sql, params)).mappings().all()
    )

    # --- by_year ---
    by_year_sql = text(
        """
        SELECT
            CAST(SUBSTR(tourney_date, 1, 4) AS INTEGER) AS label,
            COUNT(*)        AS n_bets,
            SUM(pnl_kelly)  AS sum_pnl_kelly,
            SUM(kelly_bet)  AS sum_kelly_bet,
            SUM(pnl_flat)   AS sum_pnl_flat,
            SUM(flat_bet)   AS sum_flat_bet
        FROM backtest_results
        WHERE kelly_bet > 0
          AND model_version = :model
        GROUP BY CAST(SUBSTR(tourney_date, 1, 4) AS INTEGER)
        ORDER BY label
        """
    )
    by_year = _breakdown_rows((await db.execute(by_year_sql, params)).mappings().all())

    # --- by_ev_bucket ---
    by_ev_sql = text(
        """
        SELECT
            CASE
                WHEN ev >= 0.10 THEN '10%+'
                WHEN ev >= 0.05 THEN '5-10%'
                WHEN ev >= 0.02 THEN '2-5%'
                ELSE '0-2%'
            END AS label,
            COUNT(*)        AS n_bets,
            SUM(pnl_kelly)  AS sum_pnl_kelly,
            SUM(kelly_bet)  AS sum_kelly_bet,
            SUM(pnl_flat)   AS sum_pnl_flat,
            SUM(flat_bet)   AS sum_flat_bet
        FROM backtest_results
        WHERE kelly_bet > 0
          AND model_version = :model
        GROUP BY label
        ORDER BY label
        """
    )
    by_ev_bucket = _breakdown_rows((await db.execute(by_ev_sql, params)).mappings().all())

    # --- by_rank_tier ---
    # bet-on player rank: outcome=1 => winner_rank, outcome=0 => loser_rank
    by_rank_sql = text(
        """
        SELECT
            CASE
                WHEN CASE WHEN outcome = 1 THEN winner_rank ELSE loser_rank END <= 10  THEN 'Top 10'
                WHEN CASE WHEN outcome = 1 THEN winner_rank ELSE loser_rank END <= 50  THEN '11-50'
                WHEN CASE WHEN outcome = 1 THEN winner_rank ELSE loser_rank END <= 100 THEN '51-100'
                ELSE '100+'
            END AS label,
            COUNT(*)        AS n_bets,
            SUM(pnl_kelly)  AS sum_pnl_kelly,
            SUM(kelly_bet)  AS sum_kelly_bet,
            SUM(pnl_flat)   AS sum_pnl_flat,
            SUM(flat_bet)   AS sum_flat_bet
        FROM backtest_results
        WHERE kelly_bet > 0
          AND model_version = :model
        GROUP BY label
        ORDER BY label
        """
    )
    by_rank_tier = _breakdown_rows((await db.execute(by_rank_sql, params)).mappings().all())

    return BacktestSummary(
        n_bets=n_bets,
        kelly_roi=kelly_roi,
        flat_roi=flat_roi,
        total_pnl_kelly=total_pnl_kelly,
        total_pnl_flat=total_pnl_flat,
        by_surface=by_surface,
        by_tourney_level=by_tourney_level,
        by_year=by_year,
        by_ev_bucket=by_ev_bucket,
        by_rank_tier=by_rank_tier,
    )


# ---------------------------------------------------------------------------
# GET /backtest/bets — paginated bet rows
# ---------------------------------------------------------------------------

@router.get("/bets", response_model=PaginatedBetsResponse)
async def get_backtest_bets(
    db: DbDep,
    offset: int = 0,
    limit: int = Query(default=50, le=500),
    model: str = "logistic_v1",
    surface: Optional[str] = None,
    year: Optional[int] = None,
    min_ev: Optional[float] = None,
    tourney_level: Optional[str] = None,
) -> PaginatedBetsResponse:
    """Return paginated individual backtest bet rows with optional filters."""
    conditions: List[str] = [
        "kelly_bet > 0",
        "model_version = :model",
    ]
    params: dict = {"model": model, "offset": offset, "limit": limit}

    if surface is not None:
        conditions.append("surface = :surface")
        params["surface"] = surface

    if year is not None:
        conditions.append("CAST(SUBSTR(tourney_date, 1, 4) AS INTEGER) = :year")
        params["year"] = year

    if min_ev is not None:
        conditions.append("ev >= :min_ev")
        params["min_ev"] = min_ev

    if tourney_level is not None:
        conditions.append("tourney_level = :tourney_level")
        params["tourney_level"] = tourney_level

    where = " AND ".join(conditions)

    count_sql = text(f"SELECT COUNT(*) AS total FROM backtest_results WHERE {where}")
    total_row = (await db.execute(count_sql, params)).mappings().one()
    total = total_row["total"] or 0

    data_sql = text(
        f"""
        SELECT
            id, fold_year, tourney_id, match_num, tour, model_version,
            player_id, outcome, calibrated_prob, decimal_odds, ev,
            kelly_bet, pnl_kelly, pnl_flat, bankroll_before, bankroll_after,
            surface, tourney_level, tourney_date
        FROM backtest_results
        WHERE {where}
        ORDER BY tourney_date, id
        LIMIT :limit OFFSET :offset
        """
    )
    rows = (await db.execute(data_sql, params)).mappings().all()

    data = [
        BacktestBetRow(
            id=row["id"],
            fold_year=row["fold_year"],
            tourney_id=row["tourney_id"],
            match_num=row["match_num"],
            tour=row["tour"],
            model_version=row["model_version"],
            player_id=row["player_id"],
            outcome=row["outcome"],
            calibrated_prob=row["calibrated_prob"],
            decimal_odds=row["decimal_odds"],
            ev=row["ev"],
            kelly_bet=row["kelly_bet"],
            pnl_kelly=row["pnl_kelly"],
            pnl_flat=row["pnl_flat"],
            bankroll_before=row["bankroll_before"],
            bankroll_after=row["bankroll_after"],
            surface=row["surface"],
            tourney_level=row["tourney_level"],
            tourney_date=row["tourney_date"],
        )
        for row in rows
    ]

    return PaginatedBetsResponse(total=total, offset=offset, limit=limit, data=data)
