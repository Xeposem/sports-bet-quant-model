"""
GET /api/v1/calibration — returns calibration reliability diagram data.

Parameters:
  model  — model_version filter (default: logistic_v1)
  fold   — optional fold_label filter; if omitted returns 'overall' fold or latest

bin_midpoints and empirical_freq are stored as JSON text in the DB and parsed
with json.loads() before constructing CalibrationBin instances.
"""

from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from src.api.deps import DbDep
from src.api.schemas import CalibrationBin, CalibrationResponse

router = APIRouter(prefix="/calibration", tags=["calibration"])


@router.get("", response_model=CalibrationResponse)
async def get_calibration(
    db: DbDep,
    model: str = "logistic_v1",
    fold: Optional[str] = None,
) -> CalibrationResponse:
    """Return calibration curve data for the given model and optional fold."""
    params: dict = {"model": model}

    if fold is not None:
        sql = text(
            """
            SELECT fold_label, bin_midpoints, empirical_freq, n_samples
            FROM calibration_data
            WHERE model_version = :model
              AND fold_label = :fold
            LIMIT 1
            """
        )
        params["fold"] = fold
        row = (await db.execute(sql, params)).mappings().first()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"No calibration data for model={model}, fold={fold}",
            )
        selected = row
    else:
        # Prefer 'overall' fold; fall back to most recently computed
        overall_sql = text(
            """
            SELECT fold_label, bin_midpoints, empirical_freq, n_samples
            FROM calibration_data
            WHERE model_version = :model
              AND fold_label = 'overall'
            LIMIT 1
            """
        )
        row = (await db.execute(overall_sql, params)).mappings().first()

        if row is not None:
            selected = row
        else:
            latest_sql = text(
                """
                SELECT fold_label, bin_midpoints, empirical_freq, n_samples
                FROM calibration_data
                WHERE model_version = :model
                ORDER BY computed_at DESC
                LIMIT 1
                """
            )
            row = (await db.execute(latest_sql, params)).mappings().first()
            if row is None:
                return CalibrationResponse(
                    model_version=model,
                    fold=None,
                    bins=[],
                )
            selected = row

    midpoints: List[float] = json.loads(selected["bin_midpoints"])
    emp_freqs: List[float] = json.loads(selected["empirical_freq"])
    n_samples_total: int = selected["n_samples"]

    # Distribute n_samples evenly across bins as approximation
    n_bins = len(midpoints)
    per_bin = n_samples_total // n_bins if n_bins else 0

    bins: List[CalibrationBin] = [
        CalibrationBin(
            midpoint=mid,
            empirical_freq=freq,
            n_samples=per_bin,
        )
        for mid, freq in zip(midpoints, emp_freqs)
    ]

    return CalibrationResponse(
        model_version=model,
        fold=selected["fold_label"],
        bins=bins,
    )
