"""
In-memory job state management for background tasks.

Provides simple UUID-keyed state tracking for long-running jobs
such as data refresh and backtest runs. State lives only in memory
(reset on server restart); no persistence needed for v1.

Exports:
    job_states: dict[str, dict]  -- module-level state store
    create_job(job_type) -> str  -- create and register a new job
    update_job(job_id, **kwargs) -- merge kwargs into existing job state
    get_job(job_id) -> dict | None -- retrieve job state or None
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

# Module-level state store. All running/completed job states live here.
job_states: dict[str, dict] = {}

# Cancellation events keyed by job_id.
_cancel_events: dict[str, threading.Event] = {}


def create_job(job_type: str) -> str:
    """Create a new job entry and return its UUID.

    Args:
        job_type: Human-readable type label (e.g. 'refresh', 'backtest').

    Returns:
        str: UUID string identifying the new job.
    """
    job_id = str(uuid.uuid4())
    job_states[job_id] = {
        "status": "running",
        "type": job_type,
        "step": "starting",
        "started_at": datetime.utcnow().isoformat(),
    }
    _cancel_events[job_id] = threading.Event()
    return job_id


def update_job(job_id: str, **kwargs) -> None:
    """Merge kwargs into an existing job's state dict.

    Args:
        job_id: UUID of the job to update.
        **kwargs: Key-value pairs to merge into the job state.

    Raises:
        KeyError: If job_id does not exist in job_states.
    """
    if job_id not in job_states:
        raise KeyError(f"Job not found: {job_id}")
    job_states[job_id].update(kwargs)


def get_job(job_id: str) -> Optional[dict]:
    """Return a job's state dict or None if not found.

    Args:
        job_id: UUID of the job to retrieve.

    Returns:
        dict with job state fields, or None if not found.
    """
    return job_states.get(job_id)


def cancel_job(job_id: str) -> bool:
    """Signal a job to cancel. Returns True if the job was found and signalled."""
    evt = _cancel_events.get(job_id)
    if evt is None:
        return False
    evt.set()
    return True


def is_cancelled(job_id: str) -> bool:
    """Check whether a job has been signalled to cancel."""
    evt = _cancel_events.get(job_id)
    return evt is not None and evt.is_set()
