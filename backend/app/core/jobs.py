"""
jobs.py — ARQ job definitions for async background processing.

Worker is run as a separate Railway service:
  arq app.core.jobs.WorkerSettings
"""
import logging
from typing import Any
from urllib.parse import urlparse
from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings
from app.models.org import Outlet  # noqa: F401 — required for SQLAlchemy relationship resolution
from app.models.ingestion import UploadSession, SourceFile  # noqa: F401
from app.models.records import SalesRecord, PurchaseRecord, LaborRecord  # noqa: F401
from app.models.metrics import MetricSnapshot, ActionLog             # noqa: F401

logger = logging.getLogger(__name__)

# Increment this whenever the metric output shape changes in a backwards-incompatible way.
# Old MetricSnapshots with a lower schema_version are flagged as stale in GET /metrics.
CURRENT_SCHEMA_VERSION = 1


def get_redis_settings() -> RedisSettings:
    """
    Parse REDIS_URL into ARQ RedisSettings using stdlib urlparse.

    Railway Redis URLs follow the format:
        redis://default:PASSWORD@redis.railway.internal:6379

    urlparse correctly splits this into:
        hostname = redis.railway.internal
        port     = 6379
        password = PASSWORD   (not "default:PASSWORD")

    Previously we used manual string splitting which incorrectly included
    the username ("default") as part of the password, causing AuthenticationError.
    """
    parsed = urlparse(settings.REDIS_URL)
    return RedisSettings(
        host     = parsed.hostname or "localhost",
        port     = parsed.port or 6379,
        password = parsed.password or None,   # None = no auth (local dev)
        database = int(parsed.path.lstrip("/")) if parsed.path and parsed.path != "/" else 0,
    )


# ── Job functions ─────────────────────────────────────────────────────────────

async def run_ingestion_job(ctx: dict, session_id: str) -> dict:
    """
    Background job: fingerprint → sanitise → parse → normalise → store records.
    Called after all files are uploaded to R2.
    """
    from app.core.database import AsyncSessionLocal
    from app.ingestion.pipeline import run_ingestion

    logger.info(f"[job] Starting ingestion for session {session_id}")
    async with AsyncSessionLocal() as db:
        try:
            result = await run_ingestion(db, session_id)
            logger.info(f"[job] Ingestion complete for {session_id}: {result}")
            return result
        except Exception as e:
            logger.error(f"[job] Ingestion failed for {session_id}: {e}", exc_info=True)
            raise


async def run_compute_job(ctx: dict, session_id: str, outlet_id: str, vertical: str) -> dict:
    """
    Background job: assemble metric DataFrames → run vertical metrics engine → cache results.
    """
    from app.core.database import AsyncSessionLocal
    from app.ingestion.merger import build_metric_frames
    from app.verticals.registry import get_vertical
    from app.models.ingestion import UploadSession
    from app.models.metrics import MetricSnapshot
    from sqlalchemy import select
    from datetime import datetime

    logger.info(f"[job] Starting compute for session {session_id}, vertical={vertical}")

    async with AsyncSessionLocal() as db:
        try:
            # Load outlet config for metric engine
            from app.models.org import Outlet, PlatformConfig
            outlet_result = await db.execute(select(Outlet).where(Outlet.id == outlet_id))
            outlet = outlet_result.scalar_one_or_none()
            if not outlet:
                raise ValueError(f"Outlet {outlet_id} not found")

            # Build metric-specific DataFrames from stored records
            frames = await build_metric_frames(db, session_id, outlet_id)

            # Load config for this outlet
            config = await _build_outlet_config(db, outlet)

            # Run vertical metric engine
            vertical_engine = get_vertical(vertical)
            result = vertical_engine.compute_metrics(frames, config)

            # Cache results
            snap = MetricSnapshot(
                session_id     = session_id,
                outlet_id      = outlet_id,
                vertical       = vertical,
                schema_version = CURRENT_SCHEMA_VERSION,
                computed_at    = datetime.utcnow(),
                result         = result.model_dump(),
                sufficiency    = result.sufficiency_map(),
            )
            db.add(snap)

            # Update session status
            session_result = await db.execute(
                select(UploadSession).where(UploadSession.id == session_id)
            )
            session = session_result.scalar_one_or_none()
            if session:
                session.compute_status = "done"
                session.computed_at    = datetime.utcnow()

            await db.commit()
            logger.info(f"[job] Compute complete for {session_id}")
            return {"status": "done", "session_id": session_id}

        except Exception as e:
            # Mark session as failed
            from app.models.ingestion import UploadSession
            session_result = await db.execute(
                select(UploadSession).where(UploadSession.id == session_id)
            )
            session = session_result.scalar_one_or_none()
            if session:
                session.compute_status = "failed"
                session.error_message  = str(e)
            await db.commit()
            logger.error(f"[job] Compute failed for {session_id}: {e}", exc_info=True)
            raise


async def _build_outlet_config(db, outlet) -> dict:
    """Assemble config dict for metric engine from outlet + platform configs."""
    from app.models.org import PlatformConfig
    from sqlalchemy import select

    pc_result = await db.execute(
        select(PlatformConfig).where(PlatformConfig.outlet_id == outlet.id)
    )
    platform_configs = pc_result.scalars().all()
    commission_map = {pc.platform: pc.commission_pct for pc in platform_configs}

    return {
        "outlet_id":              str(outlet.id),
        "seats":                  outlet.seats or 0,
        "opening_hours":          outlet.opening_hours or 0.0,
        "gst_rate":               outlet.gst_rate or 5.0,
        "swiggy_commission_pct":  commission_map.get("swiggy", 22.0),
        "zomato_commission_pct":  commission_map.get("zomato", 25.0),
    }


# ── ARQ worker settings ───────────────────────────────────────────────────────

class WorkerSettings:
    """ARQ worker configuration — run with: arq app.core.jobs.WorkerSettings"""
    functions = [run_ingestion_job, run_compute_job]
    redis_settings = get_redis_settings()
    max_jobs = 4
    job_timeout = 300          # 5 minutes max per job
    keep_result = 3600         # keep job results for 1 hour
    retry_jobs = True
    max_tries = 3


async def get_arq_pool():
    """Get ARQ Redis pool for enqueueing jobs from the API."""
    return await create_pool(get_redis_settings())
