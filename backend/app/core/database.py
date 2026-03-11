"""
database.py — SQLAlchemy async engine with PostgreSQL Row Level Security support.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text, event
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Convert sync postgres:// URL to async asyncpg driver
DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
).replace(
    "postgres://", "postgresql+asyncpg://"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_with_rls(outlet_id: str):
    """
    Yields a session with PostgreSQL RLS context set.
    All queries in this session are automatically scoped to outlet_id.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Set RLS context variable — DB policies use this to filter rows
            await session.execute(
                text("SET LOCAL app.current_outlet_id = :oid"),
                {"oid": str(outlet_id)}
            )
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    """Create all tables. Used in development — production uses Alembic migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created.")


async def apply_rls_policies(conn):
    """
    Apply PostgreSQL Row Level Security policies on data tables.
    Called once during initial DB setup.
    """
    rls_sql = """
    -- Enable RLS on data tables
    ALTER TABLE sales_records    ENABLE ROW LEVEL SECURITY;
    ALTER TABLE purchase_records ENABLE ROW LEVEL SECURITY;
    ALTER TABLE labor_records    ENABLE ROW LEVEL SECURITY;
    ALTER TABLE metric_snapshots ENABLE ROW LEVEL SECURITY;

    -- Policies: only rows matching current outlet context are visible
    CREATE POLICY outlet_isolation ON sales_records
        USING (outlet_id::text = current_setting('app.current_outlet_id', true));

    CREATE POLICY outlet_isolation ON purchase_records
        USING (outlet_id::text = current_setting('app.current_outlet_id', true));

    CREATE POLICY outlet_isolation ON labor_records
        USING (outlet_id::text = current_setting('app.current_outlet_id', true));

    CREATE POLICY outlet_isolation ON metric_snapshots
        USING (outlet_id::text = current_setting('app.current_outlet_id', true));
    """
    try:
        await conn.execute(text(rls_sql))
    except Exception as e:
        logger.warning(f"RLS policy setup skipped (may already exist): {e}")
