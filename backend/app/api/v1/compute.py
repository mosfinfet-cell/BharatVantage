"""
compute.py  — POST /compute/{session_id}   enqueue ARQ job (idempotent)
status.py   — GET  /status/{session_id}    poll job progress
metrics.py  — GET  /metrics/{session_id}   return v1.1 MetricSnapshot

v1.1 changes to GET /metrics:
  - Returns full v1.1 result JSON including 3-layer structure
  - schema_version bumped to 2 (v1.1 = CURRENT_SCHEMA_VERSION 2)
  - is_stale flag updated against new version constant
  - Added manual_entry endpoint for cash drawer / platform ratings
"""
from datetime import datetime, date
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_outlet, get_current_user, TokenData
from app.core.jobs import get_arq_pool
from app.models.ingestion import UploadSession
from app.models.metrics import MetricSnapshot
from app.models.org import Outlet
from app.models.ingestion import ManualEntry

compute_router = APIRouter()
status_router  = APIRouter()
metrics_router = APIRouter()
manual_router  = APIRouter()

# Must match CURRENT_SCHEMA_VERSION in jobs.py (the writer).
# Both must be updated together whenever the metric shape changes.
CURRENT_SCHEMA_VERSION = 1


# ══════════════════════════════════════════════════════════════════════════════
# COMPUTE — enqueue job
# ══════════════════════════════════════════════════════════════════════════════

class ComputeResponse(BaseModel):
    session_id: str
    job_id:     Optional[str] = None
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

    # Idempotency
    if session.compute_status in ("queued", "running"):
        return ComputeResponse(
            session_id=session_id, job_id=session.compute_job_id,
            status=session.compute_status, message="Compute job already in progress.",
        )
    if session.compute_status == "done":
        return ComputeResponse(
            session_id=session_id, job_id=session.compute_job_id,
            status="done", message="Metrics already computed. Use GET /metrics/{session_id}.",
        )
    if session.ingest_status != "done":
        raise HTTPException(400, f"Ingestion not complete (status: {session.ingest_status}).")

    # vertical = the metric engine to use. Always "restaurant" for BharatVantage v1.
    # outlet_type (hybrid / dine_in / cloud_kitchen) controls which metric GROUPS
    # are computed — that branching happens inside the engine via _build_outlet_config,
    # not here. Passing outlet_type here was the bug: registry only has "restaurant".
    pool = await get_arq_pool()
    job  = await pool.enqueue_job(
        "run_compute_job",
        session_id,
        str(outlet.id),
        "restaurant",
    )
    session.compute_status = "queued"
    session.compute_job_id = job.job_id
    await db.commit()

    return ComputeResponse(
        session_id=session_id, job_id=job.job_id,
        status="queued", message="Compute job queued. Poll GET /status/{session_id}.",
    )


# ══════════════════════════════════════════════════════════════════════════════
# STATUS
# ══════════════════════════════════════════════════════════════════════════════

class StatusResponse(BaseModel):
    session_id:      str
    ingest_status:   str
    compute_status:  str
    computed_at:     Optional[str] = None
    sources_present: list
    date_from:       Optional[str] = None
    date_to:         Optional[str] = None
    ingest_errors:   Optional[Any] = None
    error_message:   Optional[str] = None
    ready:           bool


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
        date_to         = session.date_to.isoformat()   if session.date_to   else None,
        ingest_errors   = session.ingest_errors,
        error_message   = session.error_message,
        ready           = session.compute_status == "done",
    )


# ══════════════════════════════════════════════════════════════════════════════
# METRICS — GET /metrics/{session_id}
# ══════════════════════════════════════════════════════════════════════════════

@metrics_router.get("/metrics/{session_id}")
async def get_metrics(
    session_id: str,
    outlet:     Outlet       = Depends(get_current_outlet),
    db:         AsyncSession = Depends(get_db),
):
    """
    Returns the full v1.1 MetricSnapshot.result JSON.

    Response structure:
    {
      session_id, computed_at, schema_version, is_stale,
      outlet_type,
      sufficiency:   { metric_key: 'complete'|'estimated'|'locked'|'partial' },
      alerts:        [ { priority, metric, message, color, fired_today } ],
      metrics: {
        // Layer 1 — always present for hybrid
        total_earnings, staff_cost_pct, prime_cost_pct, kitchen_conflict_days,
        channel_comparison,

        // Dine-in tab
        dine_in: { today_earnings, cash_reconciliation, avg_bill_per_table,
                   table_turns, best_service, worst_service, prime_cost_pct,
                   staff_cost_pct, staff_role_breakdown, revpash },

        // Online tab
        online: { pending_settlements, payout_bridge, platform_earnings,
                  true_order_margin, penalties, ad_spend_efficiency,
                  item_channel_margin, packaging_cost_config },

        // CA Export
        ca_export: { completeness, gst_on_sales, gst_on_commission_reverse_charge,
                     itc_on_packaging, reconciliation_gap }
      }
    }
    """
    # Verify session belongs to outlet
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
        return JSONResponse(
            status_code=202,
            content={"status": session.compute_status, "message": f"Metrics not ready. Current status: {session.compute_status}"},
        )

    snap_result = await db.execute(
        select(MetricSnapshot).where(MetricSnapshot.session_id == session_id)
    )
    snapshot = snap_result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(404, "Metric snapshot not found.")

    # Extract sufficiency and alerts from result (v1.1 embeds them)
    raw_result  = dict(snapshot.result or {})   # shallow copy — never mutate the ORM object
    sufficiency = raw_result.pop("sufficiency", snapshot.sufficiency or {})
    alerts      = raw_result.pop("alerts", [])

    return {
        "session_id":         session_id,
        "computed_at":        snapshot.computed_at.isoformat(),
        "schema_version":     snapshot.schema_version,
        "is_stale":           snapshot.schema_version < CURRENT_SCHEMA_VERSION,
        "outlet_type":        raw_result.get("outlet_type", "hybrid"),
        "period_start":       raw_result.get("period_start"),
        "period_end":         raw_result.get("period_end"),
        "sufficiency":        sufficiency,
        "alerts":             alerts,
        "alignment_warnings": session.ingest_errors,
        "metrics":            raw_result,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MANUAL ENTRIES — POST /manual-entry
# ══════════════════════════════════════════════════════════════════════════════

class ManualEntryRequest(BaseModel):
    entry_type: str    # 'cash_drawer' | 'platform_rating'
    entry_date: str    # ISO date string 'YYYY-MM-DD'
    value:      float
    platform:   Optional[str] = None   # 'swiggy' | 'zomato' — required for ratings


class ManualEntryResponse(BaseModel):
    id:         str
    entry_type: str
    entry_date: str
    value:      float
    platform:   Optional[str] = None
    created_at: str


@manual_router.post("/manual-entry", response_model=ManualEntryResponse)
async def create_manual_entry(
    body:       ManualEntryRequest,
    outlet:     Outlet       = Depends(get_current_outlet),
    db:         AsyncSession = Depends(get_db),
):
    """
    Operator-entered data for Cash Reconciliation and Platform Rating metrics.

    cash_drawer:    value = physical drawer amount (₹) for entry_date
    platform_rating: value = rating (1.0–5.0), platform = 'swiggy'|'zomato'
    """
    if body.entry_type not in ("cash_drawer", "platform_rating"):
        raise HTTPException(400, "entry_type must be 'cash_drawer' or 'platform_rating'.")
    if body.entry_type == "platform_rating":
        if not body.platform:
            raise HTTPException(400, "platform is required for platform_rating entries.")
        if not (1.0 <= body.value <= 5.0):
            raise HTTPException(400, "Platform rating must be between 1.0 and 5.0.")

    try:
        entry_date = datetime.strptime(body.entry_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "entry_date must be in YYYY-MM-DD format.")

    entry = ManualEntry(
        outlet_id  = str(outlet.id),
        entry_type = body.entry_type,
        entry_date = entry_date,
        value      = body.value,
        platform   = body.platform,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    return ManualEntryResponse(
        id         = entry.id,
        entry_type = entry.entry_type,
        entry_date = entry.entry_date.date().isoformat(),
        value      = entry.value,
        platform   = entry.platform,
        created_at = entry.created_at.isoformat(),
    )


@manual_router.get("/manual-entries")
async def list_manual_entries(
    entry_type: Optional[str] = None,
    outlet:     Outlet        = Depends(get_current_outlet),
    db:         AsyncSession  = Depends(get_db),
):
    """List manual entries for an outlet. Filter by entry_type if provided."""
    query = select(ManualEntry).where(ManualEntry.outlet_id == str(outlet.id))
    if entry_type:
        query = query.where(ManualEntry.entry_type == entry_type)
    query = query.order_by(ManualEntry.entry_date.desc()).limit(90)

    result = await db.execute(query)
    entries = result.scalars().all()

    return [
        {
            "id":         e.id,
            "entry_type": e.entry_type,
            "entry_date": e.entry_date.date().isoformat(),
            "value":      e.value,
            "platform":   e.platform,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]
