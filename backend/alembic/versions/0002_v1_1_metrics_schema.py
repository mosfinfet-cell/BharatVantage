"""
0002_v1_1_metrics_schema.py

Written against actual DB state inspected on 2026-03-15:
  - manual_entries EXISTS with wrong schema (drop + recreate)
  - outlets MISSING all v1.1 columns
  - sales_records MISSING all v1.1 columns
  - outlettype enum does NOT exist yet
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision      = '0002_v1_1_metrics_schema'
down_revision = '0001_initial'
branch_labels = None
depends_on    = None


def upgrade() -> None:

    # ── 1. outlettype enum ─────────────────────────────────────────────────
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'outlettype') THEN
                CREATE TYPE outlettype AS ENUM ('dine_in', 'hybrid', 'cloud_kitchen');
            END IF;
        END$$;
    """)

    # ── 2. outlets — add v1.1 columns ──────────────────────────────────────
    # Check each column before adding — idempotent
    op.execute("""
        ALTER TABLE outlets
            ADD COLUMN IF NOT EXISTS outlet_type            VARCHAR(20)  NOT NULL DEFAULT 'hybrid',
            ADD COLUMN IF NOT EXISTS packaging_cost_tier1   FLOAT        DEFAULT 12.0,
            ADD COLUMN IF NOT EXISTS packaging_cost_tier2   FLOAT        DEFAULT 20.0,
            ADD COLUMN IF NOT EXISTS packaging_cost_tier3   FLOAT        DEFAULT 35.0,
            ADD COLUMN IF NOT EXISTS packaging_configured   BOOLEAN      DEFAULT false,
            ADD COLUMN IF NOT EXISTS gst_rate_pct           FLOAT        DEFAULT 5.0,
            ADD COLUMN IF NOT EXISTS monthly_rent           FLOAT,
            ADD COLUMN IF NOT EXISTS monthly_utilities      FLOAT,
            ADD COLUMN IF NOT EXISTS settlement_cycle_swiggy INTEGER     DEFAULT 7,
            ADD COLUMN IF NOT EXISTS settlement_cycle_zomato INTEGER     DEFAULT 7;
    """)

    # ── 3. sales_records — add v1.1 columns ───────────────────────────────
    op.execute("""
        ALTER TABLE sales_records
            ADD COLUMN IF NOT EXISTS payment_method     VARCHAR(20),
            ADD COLUMN IF NOT EXISTS settlement_date    TIMESTAMP,
            ADD COLUMN IF NOT EXISTS settled            BOOLEAN  DEFAULT false,
            ADD COLUMN IF NOT EXISTS reason_code        VARCHAR(100),
            ADD COLUMN IF NOT EXISTS penalty_state      VARCHAR(20),
            ADD COLUMN IF NOT EXISTS service_period     VARCHAR(20),
            ADD COLUMN IF NOT EXISTS gst_on_commission  FLOAT    DEFAULT 0.0;
    """)

    # Indexes for new sales_records columns — IF NOT EXISTS is pg 9.5+
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sales_outlet_settled
            ON sales_records (outlet_id, settled);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sales_outlet_penalty_state
            ON sales_records (outlet_id, penalty_state);
    """)

    # ── 4. manual_entries — drop old schema, recreate with correct schema ──
    # Old schema had: period_from, period_to, amount, notes, entered_by
    # New schema needs: entry_date, value, platform
    op.execute("DROP TABLE IF EXISTS manual_entries CASCADE;")
    op.execute("""
        CREATE TABLE manual_entries (
            id          UUID          NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
            outlet_id   UUID          NOT NULL REFERENCES outlets(id),
            entry_type  VARCHAR(50)   NOT NULL,
            entry_date  TIMESTAMP     NOT NULL,
            platform    VARCHAR(30),
            value       FLOAT         NOT NULL,
            created_at  TIMESTAMP     DEFAULT now()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_manual_outlet_type_date
            ON manual_entries (outlet_id, entry_type, entry_date);
    """)


def downgrade() -> None:
    # Restore old manual_entries schema
    op.execute("DROP TABLE IF EXISTS manual_entries CASCADE;")
    op.execute("""
        CREATE TABLE manual_entries (
            id          UUID        NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
            outlet_id   UUID        NOT NULL REFERENCES outlets(id),
            entry_type  VARCHAR(50) NOT NULL,
            period_from TIMESTAMP,
            period_to   TIMESTAMP,
            amount      FLOAT,
            notes       TEXT,
            entered_by  UUID,
            created_at  TIMESTAMP   DEFAULT now()
        );
    """)

    # Remove sales_records v1.1 columns
    op.execute("DROP INDEX IF EXISTS ix_sales_outlet_settled;")
    op.execute("DROP INDEX IF EXISTS ix_sales_outlet_penalty_state;")
    op.execute("""
        ALTER TABLE sales_records
            DROP COLUMN IF EXISTS payment_method,
            DROP COLUMN IF EXISTS settlement_date,
            DROP COLUMN IF EXISTS settled,
            DROP COLUMN IF EXISTS reason_code,
            DROP COLUMN IF EXISTS penalty_state,
            DROP COLUMN IF EXISTS service_period,
            DROP COLUMN IF EXISTS gst_on_commission;
    """)

    # Remove outlets v1.1 columns
    op.execute("""
        ALTER TABLE outlets
            DROP COLUMN IF EXISTS outlet_type,
            DROP COLUMN IF EXISTS packaging_cost_tier1,
            DROP COLUMN IF EXISTS packaging_cost_tier2,
            DROP COLUMN IF EXISTS packaging_cost_tier3,
            DROP COLUMN IF EXISTS packaging_configured,
            DROP COLUMN IF EXISTS gst_rate_pct,
            DROP COLUMN IF EXISTS monthly_rent,
            DROP COLUMN IF EXISTS monthly_utilities,
            DROP COLUMN IF EXISTS settlement_cycle_swiggy,
            DROP COLUMN IF EXISTS settlement_cycle_zomato;
    """)

    op.execute("DROP TYPE IF EXISTS outlettype;")
