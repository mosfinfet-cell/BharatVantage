"""
pipeline.py — Ingestion pipeline orchestrator.
Called by the ARQ worker job after files are uploaded to R2.

Flow per file:
  R2 download → sanitise → fingerprint → parse → normalise → store
"""
from __future__ import annotations
import hashlib
import logging
from datetime import datetime
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.storage import storage
from app.ingestion.sanitiser import sanitise
from app.ingestion.fingerprint import detect_source
from app.models.ingestion import UploadSession, SourceFile
from app.models.records import SalesRecord, PurchaseRecord, LaborRecord

logger = logging.getLogger(__name__)


def _get_parser(source_type: str, data_category: str):
    """Return the correct parser for a source type."""
    from app.ingestion.parsers.swiggy   import SwiggyParser
    from app.ingestion.parsers.others   import (
        ZomatoParser, PetpoojaParser, TallyParser, PayrollParser, GenericParser
    )
    parsers = {
        "swiggy":   SwiggyParser(),
        "zomato":   ZomatoParser(),
        "petpooja": PetpoojaParser(),
        "tally":    TallyParser(),
        "payroll":  PayrollParser(),
        "generic":  GenericParser(),
    }
    return parsers.get(source_type, GenericParser())


async def run_ingestion(db: AsyncSession, session_id: str) -> dict:
    """
    Main ingestion pipeline for all files in a session.
    Returns summary: {succeeded, failed, records_stored, errors}
    """
    # Load session and files
    session_result = await db.execute(
        select(UploadSession).where(UploadSession.id == session_id)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise ValueError(f"Session {session_id} not found")

    files_result = await db.execute(
        select(SourceFile).where(SourceFile.session_id == session_id)
    )
    source_files = files_result.scalars().all()

    if not source_files:
        raise ValueError(f"No files found for session {session_id}")

    # Update session status
    session.ingest_status = "running"
    await db.commit()

    outlet_id  = str(session.outlet_id)
    succeeded  = []
    failed     = []
    total_records = 0
    all_errors    = []

    for sf in source_files:
        try:
            records_count = await _process_file(db, sf, outlet_id)
            sf.parse_status    = "done"
            sf.records_stored  = records_count
            total_records += records_count
            succeeded.append(sf.detected_source)
            logger.info(f"Processed {sf.filename}: {records_count} records stored")

        except Exception as e:
            sf.parse_status = "failed"
            sf.parse_error  = str(e)[:500]
            err_entry = {"filename": sf.filename, "source": sf.detected_source, "error": str(e)}
            failed.append(err_entry)
            all_errors.append(err_entry)
            logger.error(f"Failed to process {sf.filename}: {e}", exc_info=True)

    # Update session
    session.ingest_status  = "done" if succeeded else "failed"
    session.ingest_errors  = all_errors if all_errors else None
    session.source_coverage = {s: "present" for s in succeeded}
    if all_errors:
        session.error_message = f"{len(failed)} file(s) failed to parse."

    await db.commit()

    return {
        "session_id":      session_id,
        "succeeded":       succeeded,
        "failed":          [f["filename"] for f in failed],
        "records_stored":  total_records,
        "errors":          all_errors,
    }


async def _process_file(
    db:        AsyncSession,
    sf:        SourceFile,
    outlet_id: str,
) -> int:
    """Download, sanitise, parse, and store one file. Returns record count."""

    # Download from R2
    content = await storage.download(sf.storage_key)

    # Sanitise
    df, headers = sanitise(content, sf.original_name)

    # Get confirmed source type (user may have overridden auto-detection)
    source_type = sf.confirmed_source or sf.detected_source

    # Parse
    parser = _get_parser(source_type, sf.data_category)

    # Load outlet gst_rate for GST stripping
    from app.models.org import Outlet
    outlet_result = await db.execute(select(Outlet).where(Outlet.id == outlet_id))
    outlet = outlet_result.scalar_one_or_none()
    gst_rate = outlet.gst_rate if outlet else 5.0

    parse_result = parser.parse(
        df         = df,
        session_id = str(sf.session_id),
        outlet_id  = outlet_id,
        gst_rate   = gst_rate,
    )

    if parse_result.parse_errors:
        logger.warning(
            f"{sf.filename} parsed with {len(parse_result.parse_errors)} row errors: "
            f"{parse_result.parse_errors[:3]}"
        )

    # Store records in correct domain table
    await _store_records(db, parse_result)

    sf.row_count = parse_result.row_count
    return len(parse_result.records)


async def _store_records(db: AsyncSession, parse_result) -> None:
    """Bulk insert parsed records into the correct domain table."""
    if not parse_result.records:
        return

    if parse_result.data_category in ("sales_aggregator", "sales_pos", "generic"):
        db.add_all([SalesRecord(**r) for r in parse_result.records])

    elif parse_result.data_category == "purchases":
        db.add_all([PurchaseRecord(**r) for r in parse_result.records])

    elif parse_result.data_category == "labor":
        db.add_all([LaborRecord(**r) for r in parse_result.records])

    await db.flush()
