"""
Refresh pipeline endpoints — trigger background pipeline refresh and poll status.

Routes:
    POST /api/v1/refresh        — Trigger full pipeline refresh (ingest → ratings → sentiment → features).
    GET  /api/v1/refresh/status — Poll refresh job status by job_id query parameter.

Background jobs run in a thread pool via run_in_executor to avoid blocking the
async event loop. Job state is tracked in src.api.jobs.job_states (in-memory).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from src.api.schemas import JobResponse, RefreshStatusResponse
from src.refresh.runner import refresh_all

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/refresh", tags=["refresh"])


# ---------------------------------------------------------------------------
# Sync wrapper — runs in thread pool
# ---------------------------------------------------------------------------

def _run_refresh(job_id: str, db_path: str) -> None:
    """Execute the full pipeline refresh synchronously in a background thread."""
    from src.api.jobs import update_job

    try:
        update_job(job_id, step="ingest")
        result = refresh_all(db_path)
        update_job(job_id, status="complete", step="done", result=result)
    except Exception as exc:
        logger.error("Refresh job %s failed: %s", job_id, exc, exc_info=True)
        update_job(job_id, status="failed", error=str(exc))


# ---------------------------------------------------------------------------
# POST /refresh  — trigger pipeline refresh
# ---------------------------------------------------------------------------

@router.post("", response_model=JobResponse)
async def post_refresh(request: Request) -> JobResponse:
    """Trigger the full pipeline refresh as a background job. Returns job_id."""
    from src.api.jobs import create_job

    db_path: str = request.app.state.db_path
    job_id = create_job("refresh")

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_refresh, job_id, db_path)

    return JobResponse(job_id=job_id, status="running")


# ---------------------------------------------------------------------------
# GET /refresh/status  — poll job status
# ---------------------------------------------------------------------------

@router.get("/status", response_model=RefreshStatusResponse)
async def get_refresh_status(job_id: Optional[str] = None) -> RefreshStatusResponse:
    """Poll status of a refresh background job by job_id query parameter.

    If job_id is not provided and no jobs exist, returns idle status.
    """
    from src.api.jobs import get_job, job_states

    if job_id is None:
        if not job_states:
            return RefreshStatusResponse(job_id="", status="idle")
        # Return most recent job if no specific job_id requested
        latest_job_id = list(job_states.keys())[-1]
        job = job_states[latest_job_id]
        return RefreshStatusResponse(
            job_id=latest_job_id,
            status=job.get("status", "unknown"),
            step=job.get("step"),
            started_at=job.get("started_at"),
            result=job.get("result"),
        )

    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return RefreshStatusResponse(
        job_id=job_id,
        status=job.get("status", "unknown"),
        step=job.get("step"),
        started_at=job.get("started_at"),
        result=job.get("result"),
    )
