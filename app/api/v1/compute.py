"""
compute.py  — POST /api/v1/compute/{session_id}   → enqueue ARQ job (idempotent)
status.py   — GET  /api/v1/status/{session_id}    → poll job progress
metrics.py  — GET  /api/v1/metrics/{session_id}   → return results when ready
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Any

from app.core.database import get_db
from app.core.auth import get_current_outlet
from app.core.jobs import get_arq_pool
from app.models.ingestion import UploadSession
from app.models.metrics import MetricSnapshot
from app.models.org import Outlet

compute_router = APIRouter()
status_router  = APIRouter()
metrics_router = APIRouter()


# ── Compute ───────────────────────────────────────────────────────────────────

class ComputeResponse(BaseModel):
    session_id: str
    job_id:     Optional[str]
    status:     str
    message:    str


@compute_router.post("/compute/{session_id}", response_model=ComputeResponse)
async def enqueue_compute(
    session_id: str,
    outlet:     Outlet       = Depends(get_current_outlet),
    db:         AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UploadSession).where(
            UploadSession.id        == session_id,
            UploadSession.outlet_id == str(outlet.id),
            UploadSession.deleted_at.is_(None),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found.")

    # Idempotency — don't queue twice
    if session.compute_status in ("queued", "running"):
        return ComputeResponse(
            session_id = session_id,
            job_id     = session.compute_job_id,
            status     = session.compute_status,
            message    = "Compute job already in progress.",
        )

    if session.compute_status == "done":
        return ComputeResponse(
            session_id = session_id,
            job_id     = session.compute_job_id,
            status     = "done",
            message    = "Metrics already computed. Use GET /metrics/{session_id} to retrieve.",
        )

    if session.ingest_status != "done":
        raise HTTPException(400, f"Ingestion not complete (status: {session.ingest_status}). Wait for ingestion to finish.")

    # Enqueue ARQ job
    pool = await get_arq_pool()
    job  = await pool.enqueue_job(
        "run_compute_job",
        session_id,
        str(outlet.id),
        outlet.org.industry.value if outlet.org else "restaurant",
    )

    session.compute_status  = "queued"
    session.compute_job_id  = job.job_id
    await db.commit()

    return ComputeResponse(
        session_id = session_id,
        job_id     = job.job_id,
        status     = "queued",
        message    = "Compute job queued. Poll GET /status/{session_id} for progress.",
    )


# ── Status ────────────────────────────────────────────────────────────────────

class StatusResponse(BaseModel):
    session_id:     str
    ingest_status:  str
    compute_status: str
    computed_at:    Optional[str]
    sources_present: list
    date_from:      Optional[str]
    date_to:        Optional[str]
    ingest_errors:  Optional[Any]
    error_message:  Optional[str]
    ready:          bool


@status_router.get("/status/{session_id}", response_model=StatusResponse)
async def get_status(
    session_id: str,
    outlet:     Outlet       = Depends(get_current_outlet),
    db:         AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UploadSession).where(
            UploadSession.id        == session_id,
            UploadSession.outlet_id == str(outlet.id),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found.")

    return StatusResponse(
        session_id      = session_id,
        ingest_status   = session.ingest_status,
        compute_status  = session.compute_status,
        computed_at     = session.computed_at.isoformat() if session.computed_at else None,
        sources_present = list(session.source_coverage.keys()) if session.source_coverage else [],
        date_from       = session.date_from.isoformat() if session.date_from else None,
        date_to         = session.date_to.isoformat() if session.date_to else None,
        ingest_errors   = session.ingest_errors,
        error_message   = session.error_message,
        ready           = session.compute_status == "done",
    )


# ── Metrics ───────────────────────────────────────────────────────────────────

@metrics_router.get("/metrics/{session_id}")
async def get_metrics(
    session_id: str,
    outlet:     Outlet       = Depends(get_current_outlet),
    db:         AsyncSession = Depends(get_db),
):
    # Verify session ownership
    sess_result = await db.execute(
        select(UploadSession).where(
            UploadSession.id        == session_id,
            UploadSession.outlet_id == str(outlet.id),
        )
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found.")

    if session.compute_status != "done":
        raise HTTPException(202, f"Metrics not ready. Current status: {session.compute_status}")

    snap_result = await db.execute(
        select(MetricSnapshot).where(MetricSnapshot.session_id == session_id)
    )
    snapshot = snap_result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(404, "Metric snapshot not found.")

    return {
        "session_id":         session_id,
        "computed_at":        snapshot.computed_at.isoformat(),
        "vertical":           snapshot.vertical,
        "schema_version":     snapshot.schema_version,
        "is_stale":           snapshot.schema_version < 1,  # update RHS when CURRENT_SCHEMA_VERSION bumps
        "sufficiency":        snapshot.sufficiency,
        "alignment_warnings": session.ingest_errors,
        "metrics":            snapshot.result,
    }
