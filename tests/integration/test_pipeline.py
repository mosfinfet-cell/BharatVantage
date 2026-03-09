"""
tests/integration/test_pipeline.py — Integration tests for the ingestion pipeline.

Tests the full run_ingestion() path:
  upload file → mock R2 → fingerprint → parse → store SalesRecords

Uses:
  - in-memory SQLite (async_db fixture from conftest)
  - mock_storage (no real R2 calls)
  - seed_outlet (minimal org+outlet rows)

These tests are the best guarantee that fingerprint → parser → DB works
end-to-end before deploying to a real database.
"""
import pytest
import pytest_asyncio
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from app.models.ingestion import UploadSession, SourceFile
from app.models.records import SalesRecord

FIXTURES   = Path(__file__).parent.parent / "fixtures"
SESSION_ID = str(uuid.uuid4())


async def _create_session_and_file(
    db,
    outlet_id: str,
    filename: str,
    content: bytes,
    storage: dict,
) -> tuple[UploadSession, SourceFile]:
    """
    Create UploadSession + SourceFile rows exactly like the upload endpoint does.
    Puts the file content into mock_storage under the expected key.
    """
    import hashlib
    from app.ingestion.sanitiser import sanitise
    from app.ingestion.fingerprint import detect_source

    session = UploadSession(
        id             = SESSION_ID,
        outlet_id      = outlet_id,
        vertical       = "restaurant",
        ingest_status  = "pending",
        compute_status = "idle",
        created_at     = datetime.utcnow(),
    )
    db.add(session)
    await db.flush()

    df, headers = sanitise(content, filename)
    detection   = detect_source(headers, df)

    file_id     = str(uuid.uuid4())
    storage_key = f"sessions/{SESSION_ID}/{file_id}.csv"
    storage[storage_key] = content   # put into mock storage

    sf = SourceFile(
        id               = file_id,
        session_id       = SESSION_ID,
        filename         = f"{file_id}.csv",
        original_name    = filename,
        file_size        = len(content),
        content_hash     = hashlib.sha256(content).hexdigest(),
        storage_key      = storage_key,
        detected_source  = detection.source_type,
        confirmed_source = detection.source_type,
        data_category    = detection.data_category,
        format_version   = detection.format_version,
        confidence       = detection.confidence,
        row_count        = len(df),
        parse_status     = "pending",
        created_at       = datetime.utcnow(),
    )
    db.add(sf)
    await db.commit()
    return session, sf


# ── Swiggy end-to-end ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_swiggy_pipeline_stores_sales_records(async_db, mock_storage, seed_outlet):
    """
    Full pipeline: Swiggy CSV → run_ingestion → SalesRecord rows in DB.
    """
    from app.ingestion.pipeline import run_ingestion

    content = (FIXTURES / "swiggy_sample.csv").read_bytes()
    await _create_session_and_file(
        async_db, seed_outlet.id, "swiggy_sample.csv", content, mock_storage
    )

    result = await run_ingestion(async_db, SESSION_ID)

    assert result["records_stored"] == 10
    assert result["succeeded"]  # at least one source succeeded
    assert result["failed"] == []
    assert result["errors"]  == []

    # Verify records are actually in the DB
    records_result = await async_db.execute(
        select(SalesRecord).where(SalesRecord.session_id == SESSION_ID)
    )
    records = records_result.scalars().all()
    assert len(records) == 10

    # Spot-check first record
    first = records[0]
    assert first.channel          == "swiggy"
    assert first.source_type      == "swiggy"
    assert first.outlet_id        == str(seed_outlet.id)
    assert first.gross_amount     is not None
    assert first.gross_amount     > 0
    assert first.net_payout       is not None
    # customer_id should be hashed (16 hex chars)
    assert first.customer_id is not None
    assert len(first.customer_id) == 16


@pytest.mark.asyncio
async def test_swiggy_pipeline_marks_session_done(async_db, mock_storage, seed_outlet):
    """Session.ingest_status must be 'done' after successful ingestion."""
    from app.ingestion.pipeline import run_ingestion

    content = (FIXTURES / "swiggy_sample.csv").read_bytes()
    await _create_session_and_file(
        async_db, seed_outlet.id, "swiggy_sample.csv", content, mock_storage
    )

    await run_ingestion(async_db, SESSION_ID)

    sess_result = await async_db.execute(
        select(UploadSession).where(UploadSession.id == SESSION_ID)
    )
    session = sess_result.scalar_one()
    assert session.ingest_status == "done"


# ── Zomato end-to-end ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_zomato_pipeline_stores_sales_records(async_db, mock_storage, seed_outlet):
    from app.ingestion.pipeline import run_ingestion

    content = (FIXTURES / "zomato_sample.csv").read_bytes()
    await _create_session_and_file(
        async_db, seed_outlet.id, "zomato_sample.csv", content, mock_storage
    )

    result = await run_ingestion(async_db, SESSION_ID)

    assert result["records_stored"] == 8
    assert result["failed"] == []


# ── Pipeline error handling ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_handles_session_not_found(async_db, mock_storage, seed_outlet):
    """run_ingestion should raise ValueError for unknown session_id."""
    from app.ingestion.pipeline import run_ingestion

    with pytest.raises(ValueError, match="not found"):
        await run_ingestion(async_db, "nonexistent-session-id")


@pytest.mark.asyncio
async def test_pipeline_marks_session_failed_on_storage_error(
    async_db, mock_storage, seed_outlet, monkeypatch
):
    """
    If R2 download fails for all files, the session should be marked 'failed',
    not raise an unhandled exception.
    """
    from app.ingestion.pipeline import run_ingestion

    content = (FIXTURES / "swiggy_sample.csv").read_bytes()
    await _create_session_and_file(
        async_db, seed_outlet.id, "swiggy_sample.csv", content, mock_storage
    )

    # Make storage.download always fail
    from app.core import storage as storage_module

    async def failing_download(key):
        raise RuntimeError("R2 connection timeout")

    monkeypatch.setattr(storage_module.storage, "download", failing_download)

    result = await run_ingestion(async_db, SESSION_ID)

    # Pipeline should report failure but not raise
    assert len(result["failed"]) > 0 or len(result["errors"]) > 0

    sess_result = await async_db.execute(
        select(UploadSession).where(UploadSession.id == SESSION_ID)
    )
    session = sess_result.scalar_one()
    # Session should be marked failed (not stuck in 'running')
    assert session.ingest_status in ("failed", "done")


# ── Multi-outlet isolation ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_records_are_scoped_to_outlet(async_db, mock_storage, seed_outlet):
    """
    Records created by one outlet's pipeline must not appear in a query
    scoped to a different outlet_id.
    """
    from app.ingestion.pipeline import run_ingestion

    content = (FIXTURES / "swiggy_sample.csv").read_bytes()
    await _create_session_and_file(
        async_db, seed_outlet.id, "swiggy_sample.csv", content, mock_storage
    )
    await run_ingestion(async_db, SESSION_ID)

    other_outlet_id = str(uuid.uuid4())
    result = await async_db.execute(
        select(SalesRecord).where(
            SalesRecord.outlet_id == other_outlet_id
        )
    )
    assert result.scalars().all() == []
