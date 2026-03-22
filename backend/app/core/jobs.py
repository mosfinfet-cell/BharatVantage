"""
jobs.py — ARQ job definitions for async background processing.

Worker is run as a separate Railway service:
  arq app.core.jobs.WorkerSettings

Fixes applied (2026-03-21):
  1. _build_outlet_config: pc.commission_pct → pc.base_commission_pct
     (attribute name in PlatformConfig model is base_commission_pct)

  2. run_compute_job except block: now opens a FRESH AsyncSession to write
     the failure status. When the original db session hits a DB error,
     PostgreSQL marks that connection's transaction as aborted — any further
     queries on the same session raise InFailedSQLTransactionError.
     Using a fresh session avoids this cascading failure entirely.

  3. _build_outlet_config: wrapped in try/except so a missing or empty
     platform_configs table (e.g. new outlet with no config yet) falls back
     to sensible defaults instead of crashing the entire compute job.
"""
import logging
from typing import Any
from urllib.parse import urlparse
from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings
import app.models  # noqa: F401 — registers all SQLAlchemy models

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

    Transaction safety: the main try block uses `db`. If any query inside fails,
    PostgreSQL aborts that transaction and all further queries on `db` raise
    InFailedSQLTransactionError. To reliably write the failure status we open a
    SEPARATE session (`fail_db`) in the except block — completely independent of
    the poisoned session.
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
            # ── 1. Load outlet ────────────────────────────────────────────────
            from app.models.org import Outlet
            outlet_result = await db.execute(select(Outlet).where(Outlet.id == outlet_id))
            outlet = outlet_result.scalar_one_or_none()
            if not outlet:
                raise ValueError(f"Outlet {outlet_id} not found")

            # ── 2. Build metric DataFrames from stored records ─────────────────
            frames = await build_metric_frames(db, session_id, outlet_id)

            # ── 3. Load outlet config (commission rates, seats, etc.) ──────────
            config = await _build_outlet_config(db, outlet)

            # ── 4. Run vertical metric engine ──────────────────────────────────
            vertical_engine = get_vertical(vertical)
            result = vertical_engine.compute_metrics(frames, config)

            # ── 5. Persist metric snapshot ─────────────────────────────────────
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

            # ── 6. Update session status to done ──────────────────────────────
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
            # ── IMPORTANT: do NOT reuse `db` here ────────────────────────────
            # If a DB error occurred above, PostgreSQL has aborted the transaction
            # on this connection. Any further query on `db` raises
            # InFailedSQLTransactionError (the cascading failure we saw in logs).
            #
            # Solution: open a completely fresh session to write the failure status.
            logger.error(f"[job] Compute failed for {session_id}: {e}", exc_info=True)

            try:
                async with AsyncSessionLocal() as fail_db:
                    fail_result = await fail_db.execute(
                        select(UploadSession).where(UploadSession.id == session_id)
                    )
                    session = fail_result.scalar_one_or_none()
                    if session:
                        session.compute_status = "failed"
                        session.error_message  = str(e)[:500]
                    await fail_db.commit()
            except Exception as inner_e:
                # If even the fresh session fails, log it — don't let it mask
                # the original error that we're about to re-raise.
                logger.error(
                    f"[job] Could not write failure status for {session_id}: {inner_e}"
                )

            raise   # re-raise original so ARQ marks the job as failed


async def _build_outlet_config(db, outlet) -> dict:
    """
    Assemble config dict for the metric engine from outlet + platform_configs rows.

    Resilience: if platform_configs has no rows for this outlet (e.g. new outlet
    that hasn't been configured yet), we fall back to sensible Indian market
    defaults (Swiggy 22%, Zomato 25%) so the compute job can still run.

    Bug fixed: was reading pc.commission_pct which does not exist on the model.
    Correct attribute name is pc.base_commission_pct (see models/org.py line 138).
    """
    from app.models.org import PlatformConfig
    from sqlalchemy import select

    commission_map = {}

    try:
        pc_result = await db.execute(
            select(PlatformConfig).where(PlatformConfig.outlet_id == outlet.id)
        )
        platform_configs = pc_result.scalars().all()

        # FIX: was pc.commission_pct — correct attribute is pc.base_commission_pct
        commission_map = {
            pc.platform: pc.base_commission_pct
            for pc in platform_configs
            if pc.base_commission_pct is not None   # skip rows with no value set yet
        }

    except Exception as e:
        # If the table query itself fails (e.g. column still missing on a staging DB),
        # log the warning and proceed with defaults so compute can still run.
        logger.warning(
            f"[job] Could not load platform_configs for outlet {outlet.id}, "
            f"using defaults. Error: {e}"
        )

    return {
        "outlet_id":              str(outlet.id),
        "seats":                  outlet.seats or 0,
        "opening_hours":          outlet.opening_hours or 0.0,
        "gst_rate":               outlet.gst_rate or 5.0,
        # Fall back to standard Indian market commission rates if not configured
        "swiggy_commission_pct":  commission_map.get("swiggy", 22.0),
        "zomato_commission_pct":  commission_map.get("zomato", 25.0),
    }


# ── ARQ worker settings ───────────────────────────────────────────────────────

class WorkerSettings:
    """ARQ worker configuration — run with: arq app.core.jobs.WorkerSettings"""
    functions      = [run_ingestion_job, run_compute_job]
    redis_settings = get_redis_settings()
    max_jobs       = 4
    job_timeout    = 300      # 5 minutes max per job
    keep_result    = 3600     # keep job results for 1 hour
    retry_jobs     = True
    max_tries      = 3


async def get_arq_pool():
    """Get ARQ Redis pool for enqueueing jobs from the API."""
    return await create_pool(get_redis_settings())
