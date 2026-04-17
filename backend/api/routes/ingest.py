"""
POST /api/ingest — Admin endpoint to manually trigger the embedding pipeline.

Runs ingestion/embedder.py in a background thread (change-detection only;
scraping and chunking must be run separately or via GitHub Actions).

Security: this endpoint is admin-only. In production, protect it with an
API key header (X-Admin-Key) or keep it behind a VPN.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["admin"])

_PROJECT   = Path(__file__).parent.parent.parent.parent   # project root
_EMBEDDER  = _PROJECT / "ingestion" / "embedder.py"

# Simple admin key check (optional; skip if ADMIN_API_KEY is not set)
_ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")

# Track running jobs (in-memory; resets on restart)
_jobs: dict[str, dict] = {}


class IngestRequest(BaseModel):
    force_full_rerun: bool = False


def _run_embedder(job_id: str, force: bool) -> None:
    """Background task: run embedder.py and record outcome in _jobs."""
    env = {**os.environ}
    if force:
        env["FORCE_FULL_RERUN"] = "true"
    env["PIPELINE_RUN_ID"] = job_id

    _jobs[job_id]["status"] = "running"

    try:
        result = subprocess.run(
            [sys.executable, str(_EMBEDDER)],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(_PROJECT),
        )
        _jobs[job_id]["status"]     = "done" if result.returncode == 0 else "failed"
        _jobs[job_id]["returncode"] = result.returncode
        _jobs[job_id]["stderr_tail"] = result.stderr[-500:] if result.stderr else ""
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except Exception as exc:
        _jobs[job_id]["status"]       = "failed"
        _jobs[job_id]["error"]        = str(exc)
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )


@router.post("/ingest", status_code=202, summary="[Admin] Trigger embedding pipeline")
def trigger_ingest(
    body:            IngestRequest       = IngestRequest(),
    background_tasks: BackgroundTasks    = BackgroundTasks(),
    x_admin_key:     Optional[str]       = Header(None, alias="X-Admin-Key"),
) -> dict:
    """
    Starts the embedder.py pipeline in the background (change-detection diff
    against ingestion_manifest.json — only NEW/UPDATED chunks are re-embedded).

    Scraping and chunking must be completed first (or run via GitHub Actions).

    Returns a job_id to poll via GET /api/ingest/{job_id}.
    """
    # Admin key check (skipped if ADMIN_API_KEY env var not set)
    if _ADMIN_API_KEY and x_admin_key != _ADMIN_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing X-Admin-Key header",
        )

    if not _EMBEDDER.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Embedder not found at {_EMBEDDER}",
        )

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id":           job_id,
        "status":           "queued",
        "force_full_rerun": body.force_full_rerun,
        "queued_at":        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    background_tasks.add_task(_run_embedder, job_id, body.force_full_rerun)

    return {
        "accepted":  True,
        "job_id":    job_id,
        "message":   "Ingestion pipeline started in background",
        "poll_url":  f"/api/ingest/{job_id}",
    }


@router.get("/ingest/{job_id}", summary="[Admin] Poll ingestion job status")
def get_ingest_status(job_id: str) -> dict:
    """Poll the status of a background ingestion job."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return job
