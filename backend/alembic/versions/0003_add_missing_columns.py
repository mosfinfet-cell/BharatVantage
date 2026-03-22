"""
0003_add_missing_columns.py

Adds columns that exist in SQLAlchemy models but were never applied
to the Railway PostgreSQL database.

Root cause: alembic stamp head was used previously to mark migrations
as complete without actually running the SQL (see Bug #2 in tech docs).

Tables patched:
  platform_configs  → base_commission_pct, settlement_cycle_days, is_active
  outlets           → outlet_type, gst_rate_pct, packaging_cost_tier1/2/3,
                      packaging_configured, monthly_rent, monthly_utilities,
                      settlement_cycle_swiggy, settlement_cycle_zomato, updated_at
  upload_sessions   → (already verified OK — listed here for completeness)

Run against Railway:
  DATABASE_URL='<railway-url>' alembic upgrade head

Then verify:
  psql <railway-url> -c "\d platform_configs"
  psql <railway-url> -c "\d outlets"
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_add_missing_columns"
down_revision = "0002_v1_1_metrics_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ── platform_configs — one statement per execute (asyncpg rule) ───────────
    op.execute("ALTER TABLE platform_configs ADD COLUMN IF NOT EXISTS base_commission_pct FLOAT")
    op.execute("ALTER TABLE platform_configs ADD COLUMN IF NOT EXISTS settlement_cycle_days INTEGER DEFAULT 7")
    op.execute("ALTER TABLE platform_configs ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
    op.execute("ALTER TABLE platform_configs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()")

    # ── outlets ───────────────────────────────────────────────────────────────
    op.execute("ALTER TABLE outlets ADD COLUMN IF NOT EXISTS outlet_type VARCHAR(20) DEFAULT 'hybrid'")
    op.execute("ALTER TABLE outlets ADD COLUMN IF NOT EXISTS gst_rate_pct FLOAT DEFAULT 5.0")
    op.execute("ALTER TABLE outlets ADD COLUMN IF NOT EXISTS packaging_cost_tier1 FLOAT DEFAULT 12.0")
    op.execute("ALTER TABLE outlets ADD COLUMN IF NOT EXISTS packaging_cost_tier2 FLOAT DEFAULT 20.0")
    op.execute("ALTER TABLE outlets ADD COLUMN IF NOT EXISTS packaging_cost_tier3 FLOAT DEFAULT 35.0")
    op.execute("ALTER TABLE outlets ADD COLUMN IF NOT EXISTS packaging_configured BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE outlets ADD COLUMN IF NOT EXISTS monthly_rent FLOAT")
    op.execute("ALTER TABLE outlets ADD COLUMN IF NOT EXISTS monthly_utilities FLOAT")
    op.execute("ALTER TABLE outlets ADD COLUMN IF NOT EXISTS settlement_cycle_swiggy INTEGER DEFAULT 7")
    op.execute("ALTER TABLE outlets ADD COLUMN IF NOT EXISTS settlement_cycle_zomato INTEGER DEFAULT 7")
    op.execute("ALTER TABLE outlets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()")

    # ── source_files ──────────────────────────────────────────────────────────
    op.execute("ALTER TABLE source_files ADD COLUMN IF NOT EXISTS data_category VARCHAR(50)")
    op.execute("ALTER TABLE source_files ADD COLUMN IF NOT EXISTS format_version VARCHAR(20)")
    op.execute("ALTER TABLE source_files ADD COLUMN IF NOT EXISTS confirmed_source VARCHAR(50)")

    # ── manual_entries — CREATE and INDEX as separate calls ───────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS manual_entries (
            id          VARCHAR(36)  PRIMARY KEY,
            outlet_id   VARCHAR(36)  NOT NULL REFERENCES outlets(id),
            entry_type  VARCHAR(50)  NOT NULL,
            entry_date  TIMESTAMP    NOT NULL,
            platform    VARCHAR(30),
            value       FLOAT        NOT NULL,
            created_at  TIMESTAMP    DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_manual_entries_outlet ON manual_entries (outlet_id)")

    # ── stock_entries ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS stock_entries (
            id                   VARCHAR(36)  PRIMARY KEY,
            outlet_id            VARCHAR(36)  NOT NULL REFERENCES outlets(id),
            period_from          TIMESTAMP    NOT NULL,
            period_to            TIMESTAMP    NOT NULL,
            opening_stock_value  FLOAT        NOT NULL DEFAULT 0.0,
            closing_stock_value  FLOAT        NOT NULL DEFAULT 0.0,
            purchases_value      FLOAT        NOT NULL DEFAULT 0.0,
            notes                TEXT,
            created_at           TIMESTAMP    DEFAULT NOW()
        )
    """)

    # ── operating_schedules ───────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS operating_schedules (
            id          VARCHAR(36)  PRIMARY KEY,
            outlet_id   VARCHAR(36)  NOT NULL REFERENCES outlets(id),
            day_of_week INTEGER      NOT NULL,
            open_time   VARCHAR(5),
            close_time  VARCHAR(5),
            is_closed   BOOLEAN      DEFAULT FALSE,
            created_at  TIMESTAMP    DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_operating_schedules_outlet ON operating_schedules (outlet_id)")


def downgrade() -> None:
    op.execute("ALTER TABLE platform_configs DROP COLUMN IF EXISTS base_commission_pct")
    op.execute("ALTER TABLE platform_configs DROP COLUMN IF EXISTS settlement_cycle_days")
    op.execute("ALTER TABLE platform_configs DROP COLUMN IF EXISTS is_active")
    op.execute("ALTER TABLE platform_configs DROP COLUMN IF EXISTS created_at")

    op.execute("ALTER TABLE outlets DROP COLUMN IF EXISTS outlet_type")
    op.execute("ALTER TABLE outlets DROP COLUMN IF EXISTS gst_rate_pct")
    op.execute("ALTER TABLE outlets DROP COLUMN IF EXISTS packaging_cost_tier1")
    op.execute("ALTER TABLE outlets DROP COLUMN IF EXISTS packaging_cost_tier2")
    op.execute("ALTER TABLE outlets DROP COLUMN IF EXISTS packaging_cost_tier3")
    op.execute("ALTER TABLE outlets DROP COLUMN IF EXISTS packaging_configured")
    op.execute("ALTER TABLE outlets DROP COLUMN IF EXISTS monthly_rent")
    op.execute("ALTER TABLE outlets DROP COLUMN IF EXISTS monthly_utilities")
    op.execute("ALTER TABLE outlets DROP COLUMN IF EXISTS settlement_cycle_swiggy")
    op.execute("ALTER TABLE outlets DROP COLUMN IF EXISTS settlement_cycle_zomato")
    op.execute("ALTER TABLE outlets DROP COLUMN IF EXISTS updated_at")

    op.execute("ALTER TABLE source_files DROP COLUMN IF EXISTS data_category")
    op.execute("ALTER TABLE source_files DROP COLUMN IF EXISTS format_version")
    op.execute("ALTER TABLE source_files DROP COLUMN IF EXISTS confirmed_source")
