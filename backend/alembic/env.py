"""
alembic/env.py — Alembic migration environment.

Uses the same async engine as the app so DATABASE_URL comes from
app.core.config.settings — one source of truth, never duplicated.

Running migrations:
    alembic upgrade head          # apply all pending migrations
    alembic revision --autogenerate -m "describe change"  # generate new migration
    alembic downgrade -1          # roll back one migration
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── Import all models so Alembic can see every table ─────────────────────────
# This is the single place where we ensure autogenerate finds every model.
# Add new model modules here as they are created.
from app.core.database import Base          # noqa: F401 — registers Base.metadata
from app.models.org        import (          # noqa: F401
    Organization, User, Outlet, PlatformConfig, OperatingSchedule
)
from app.models.ingestion  import (          # noqa: F401
    UploadSession, SourceFile, ManualEntry, StockEntry
)
from app.models.records    import (          # noqa: F401
    SalesRecord, PurchaseRecord, LaborRecord, ItemMaster
)
from app.models.metrics    import (          # noqa: F401
    MetricSnapshot, ActionLog
)

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """
    Read DATABASE_URL from app settings and convert to asyncpg driver.
    This ensures Alembic always uses the same URL as the running app.
    """
    from app.core.config import settings
    url = settings.DATABASE_URL
    # Alembic needs the +asyncpg driver for async migrations
    url = url.replace("postgresql://", "postgresql+asyncpg://")
    url = url.replace("postgres://", "postgresql+asyncpg://")
    return url


# ── Offline migrations (generate SQL without a live DB) ──────────────────────

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — emits SQL to stdout.
    Useful for generating SQL scripts to review before applying.
    """
    url = get_url()
    context.configure(
        url                     = url,
        target_metadata         = target_metadata,
        literal_binds           = True,
        dialect_opts            = {"paramstyle": "named"},
        compare_type            = True,   # detect column type changes
        compare_server_default  = True,   # detect default value changes
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations (run against live DB) ───────────────────────────────────

def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection              = connection,
        target_metadata         = target_metadata,
        compare_type            = True,
        compare_server_default  = True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async engine (required for asyncpg)."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix          = "sqlalchemy.",
        poolclass       = pool.NullPool,    # no connection pool for migrations
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ── Entry point ───────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
