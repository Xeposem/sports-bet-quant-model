"""
GET /api/v1/models — returns per-model performance metrics.

Aggregates from backtest_results (n_bets, roi) and predictions (brier, log_loss).
Derives calibration_quality from brier_score heuristic.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from sqlalchemy import text

from src.api.deps import DbDep
from src.api.schemas import ModelMetrics, ModelsResponse

router = APIRouter(prefix="/models", tags=["models"])


def _calibration_quality(brier: Optional[float]) -> Optional[str]:
    """Heuristic quality label from brier score."""
    if brier is None:
        return None
    if brier < 0.20:
        return "excellent"
    if brier < 0.25:
        return "good"
    if brier < 0.30:
        return "fair"
    return "poor"


@router.get("", response_model=ModelsResponse)
async def get_models(db: DbDep) -> ModelsResponse:
    """Return per-model metrics across all available model versions."""
    # Distinct model versions from backtest_results
    versions_sql = text(
        "SELECT DISTINCT model_version FROM backtest_results ORDER BY model_version"
    )
    version_rows = (await db.execute(versions_sql)).scalars().all()

    # Also check predictions table for models not in backtest_results
    pred_versions_sql = text(
        "SELECT DISTINCT model_version FROM predictions ORDER BY model_version"
    )
    pred_version_rows = (await db.execute(pred_versions_sql)).scalars().all()

    all_versions = sorted(set(list(version_rows) + list(pred_version_rows)))

    if not all_versions:
        return ModelsResponse(data=[])

    # Aggregate backtest stats per model
    bt_sql = text(
        """
        SELECT
            model_version,
            COUNT(*)        AS n_bets,
            SUM(pnl_kelly)  AS sum_pnl_kelly,
            SUM(kelly_bet)  AS sum_kelly_bet,
            SUM(pnl_flat)   AS sum_pnl_flat,
            SUM(flat_bet)   AS sum_flat_bet
        FROM backtest_results
        WHERE kelly_bet > 0
        GROUP BY model_version
        """
    )
    bt_rows = {row["model_version"]: row for row in (await db.execute(bt_sql)).mappings().all()}

    # Aggregate prediction quality metrics per model
    pred_sql = text(
        """
        SELECT
            model_version,
            AVG(brier_contribution) AS avg_brier,
            AVG(log_loss_contribution) AS avg_log_loss
        FROM predictions
        GROUP BY model_version
        """
    )
    pred_rows = {row["model_version"]: row for row in (await db.execute(pred_sql)).mappings().all()}

    data: List[ModelMetrics] = []
    for mv in all_versions:
        bt = bt_rows.get(mv)
        pr = pred_rows.get(mv)

        n_bets = int(bt["n_bets"]) if bt else 0

        kelly_stake = (bt["sum_kelly_bet"] or 0.0) if bt else 0.0
        flat_stake = (bt["sum_flat_bet"] or 0.0) if bt else 0.0
        kelly_roi = (
            ((bt["sum_pnl_kelly"] or 0.0) / kelly_stake) if kelly_stake else None
        )
        flat_roi = (
            ((bt["sum_pnl_flat"] or 0.0) / flat_stake) if flat_stake else None
        )

        brier = pr["avg_brier"] if pr else None
        log_loss = pr["avg_log_loss"] if pr else None

        data.append(
            ModelMetrics(
                model_version=mv,
                brier_score=brier,
                log_loss=log_loss,
                calibration_quality=_calibration_quality(brier),
                kelly_roi=kelly_roi,
                flat_roi=flat_roi,
                total_bets=n_bets,
            )
        )

    return ModelsResponse(data=data)
