"""
conftest.py — Shared pytest fixtures.

Provides:
  - async_db:     in-memory SQLite session (no PostgreSQL needed for unit tests)
  - mock_storage: replaces StorageClient with an in-memory dict
  - seed_outlet:  creates the minimal DB rows needed to test the pipeline
"""
import asyncio
import io
import pytest
import pytest_asyncio
import pandas as pd
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

# ── Use SQLite for tests (no PostgreSQL required) ──────────────────────────────
# SQLite does not support UUID(), JSON natively, so we use String for both.
# All model columns already use String(36) for UUID — no changes needed.

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for all async tests in the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_db():
    """
    Yield a fresh in-memory SQLite AsyncSession per test.
    All tables are created fresh and dropped after each test.
    """
    from app.core.database import Base

    # Import all models so Base.metadata has them
    import app.models.org           # noqa: F401
    import app.models.ingestion     # noqa: F401
    import app.models.records       # noqa: F401
    import app.models.metrics       # noqa: F401
    import app.models.refresh_tokens  # noqa: F401

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        # SQLite needs JSON columns emulated
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession,
                                         expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def mock_storage(monkeypatch):
    """
    Replace storage.upload / storage.download with in-memory dict.
    Keyed by storage_key. This prevents any real R2 calls in tests.
    """
    _store: dict[str, bytes] = {}

    async def fake_upload(content, session_id, filename, content_type="application/octet-stream"):
        key = f"sessions/{session_id}/{filename}"
        _store[key] = content
        return key

    async def fake_download(key):
        if key not in _store:
            raise FileNotFoundError(f"Not in mock storage: {key}")
        return _store[key]

    from app.core import storage as storage_module
    monkeypatch.setattr(storage_module.storage, "upload",   fake_upload)
    monkeypatch.setattr(storage_module.storage, "download", fake_download)

    return _store


@pytest_asyncio.fixture
async def seed_outlet(async_db):
    """
    Insert a minimal org + outlet row into the test DB.
    Returns the outlet ORM object — tests use outlet.id freely.
    """
    import uuid
    from app.models.org import Organization, Outlet, Industry, Plan

    org = Organization(
        id         = str(uuid.uuid4()),
        name       = "Test Org",
        industry   = Industry.RESTAURANT,
        plan       = Plan.FREE,
        created_at = datetime.utcnow(),
    )
    async_db.add(org)
    await async_db.flush()

    outlet = Outlet(
        id            = str(uuid.uuid4()),
        org_id        = org.id,
        name          = "Test Outlet",
        city          = "Pune",
        seats         = 50,
        opening_hours = 14.0,
        gst_rate      = 5.0,
        created_at    = datetime.utcnow(),
        updated_at    = datetime.utcnow(),
    )
    async_db.add(outlet)
    await async_db.commit()
    return outlet
