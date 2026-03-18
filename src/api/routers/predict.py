"""
GET /api/v1/predict — returns positive-EV prediction rows from the predictions table.

Filters:
  model     — filter by model_version (default: logistic_v1)
  min_ev    — minimum ev_value threshold (default: 0.0, positive-EV only)
  surface   — filter by surface via join to matches (optional)
  date_from — filter by predicted_at >= date_from (optional, ISO date string)
  date_to   — filter by predicted_at <= date_to (optional, ISO date string)

Returns empty data list when no matching rows exist (not 404).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from sqlalchemy import text

from src.api.deps import DbDep
from src.api.schemas import PredictResponse, PredictionRow

router = APIRouter(prefix="/predict", tags=["predict"])


@router.get("", response_model=PredictResponse)
async def get_predictions(
    db: DbDep,
    model: str = "logistic_v1",
    min_ev: float = 0.0,
    surface: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> PredictResponse:
    """Return prediction rows with positive EV, filtered by the supplied parameters."""
    conditions: List[str] = [
        "p.ev_value > 0",
        "p.model_version = :model",
        "p.ev_value >= :min_ev",
    ]
    params: dict = {"model": model, "min_ev": min_ev}

    if surface is not None:
        conditions.append(
            "EXISTS ("
            "  SELECT 1 FROM matches m"
            "  WHERE m.tourney_id = p.tourney_id"
            "    AND m.match_num  = p.match_num"
            "    AND m.tour       = p.tour"
            "    AND m.tourney_id IN ("
            "      SELECT t.tourney_id FROM tournaments t"
            "      WHERE t.surface = :surface AND t.tour = p.tour"
            "    )"
            ")"
        )
        params["surface"] = surface

    if date_from is not None:
        conditions.append("p.predicted_at >= :date_from")
        params["date_from"] = date_from

    if date_to is not None:
        conditions.append("p.predicted_at <= :date_to")
        params["date_to"] = date_to

    where = " AND ".join(conditions)
    sql = text(
        f"""
        SELECT
            p.tourney_id,
            p.match_num,
            p.tour,
            p.player_id,
            p.model_version,
            p.calibrated_prob,
            p.ev_value,
            p.edge,
            p.decimal_odds,
            p.predicted_at
        FROM predictions p
        WHERE {where}
        ORDER BY p.ev_value DESC
        """
    )

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    data = [
        PredictionRow(
            tourney_id=row["tourney_id"],
            match_num=row["match_num"],
            tour=row["tour"],
            player_id=row["player_id"],
            model_version=row["model_version"],
            calibrated_prob=row["calibrated_prob"],
            ev_value=row["ev_value"],
            edge=row["edge"],
            decimal_odds=row["decimal_odds"],
            predicted_at=row["predicted_at"],
        )
        for row in rows
    ]

    return PredictResponse(data=data)
