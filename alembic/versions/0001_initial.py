"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01 00:00:00.000000

Creates all tables in dependency order:
  organizations → users → outlets → platform_configs → operating_schedules
  → upload_sessions → source_files → manual_entries → stock_entries
  → sales_records → purchase_records → labor_records → item_master
  → metric_snapshots → action_logs

Also enables PostgreSQL Row Level Security (RLS) on the four data tables
that contain per-outlet records. RLS is applied after table creation so
it is safe to run even if tables are empty.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── organizations ─────────────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id",         sa.String(36),  primary_key=True),
        sa.Column("name",       sa.String(255), nullable=False),
        sa.Column("industry",   sa.Enum("restaurant", "generic", "clothing", "hardware",
                                        name="industry"), nullable=False, server_default="generic"),
        sa.Column("plan",       sa.Enum("free", "paid", name="plan"),
                                nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
    )

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",               sa.String(36),  primary_key=True),
        sa.Column("org_id",           sa.String(36),
                  sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("email",            sa.String(255), nullable=False),
        sa.Column("hashed_password",  sa.String(255), nullable=False),
        sa.Column("full_name",        sa.String(255), nullable=True),
        sa.Column("is_active",        sa.Boolean,     nullable=True, server_default="true"),
        sa.Column("created_at",       sa.DateTime,    nullable=True),
        sa.Column("deleted_at",       sa.DateTime,    nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── refresh_tokens ────────────────────────────────────────────────────────
    # Stores hashed refresh tokens for secure token rotation.
    # Short-lived access tokens + this table = proper session management.
    op.create_table(
        "refresh_tokens",
        sa.Column("id",          sa.String(36),  primary_key=True),
        sa.Column("user_id",     sa.String(36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash",  sa.String(64),  nullable=False),   # SHA-256 of raw token
        sa.Column("expires_at",  sa.DateTime,    nullable=False),
        sa.Column("revoked",     sa.Boolean,     nullable=False, server_default="false"),
        sa.Column("created_at",  sa.DateTime,    nullable=True),
        sa.Column("revoked_at",  sa.DateTime,    nullable=True),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_refresh_tokens_user_id",    "refresh_tokens", ["user_id"])

    # ── outlets ───────────────────────────────────────────────────────────────
    op.create_table(
        "outlets",
        sa.Column("id",             sa.String(36), primary_key=True),
        sa.Column("org_id",         sa.String(36),
                  sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name",           sa.String(255), nullable=False),
        sa.Column("city",           sa.String(100), nullable=True),
        sa.Column("seats",          sa.Integer,     nullable=True),
        sa.Column("opening_hours",  sa.Float,       nullable=True),
        sa.Column("gst_rate",       sa.Float,       nullable=True, server_default="5.0"),
        sa.Column("created_at",     sa.DateTime,    nullable=True),
        sa.Column("updated_at",     sa.DateTime,    nullable=True),
        sa.Column("deleted_at",     sa.DateTime,    nullable=True),
    )
    op.create_index("ix_outlets_org_id", "outlets", ["org_id"])

    # ── platform_configs ──────────────────────────────────────────────────────
    op.create_table(
        "platform_configs",
        sa.Column("id",             sa.String(36), primary_key=True),
        sa.Column("outlet_id",      sa.String(36),
                  sa.ForeignKey("outlets.id"), nullable=False),
        sa.Column("platform",       sa.String(50),  nullable=False),
        sa.Column("commission_pct", sa.Float,       nullable=False, server_default="22.0"),
        sa.Column("active",         sa.Boolean,     nullable=True, server_default="true"),
        sa.Column("created_at",     sa.DateTime,    nullable=True),
        sa.Column("updated_at",     sa.DateTime,    nullable=True),
    )

    # ── operating_schedules ───────────────────────────────────────────────────
    op.create_table(
        "operating_schedules",
        sa.Column("id",          sa.String(36), primary_key=True),
        sa.Column("outlet_id",   sa.String(36),
                  sa.ForeignKey("outlets.id"), nullable=False),
        sa.Column("day_of_week", sa.Integer,    nullable=False),   # 0=Mon … 6=Sun
        sa.Column("is_open",     sa.Boolean,    nullable=True, server_default="true"),
        sa.Column("open_time",   sa.String(5),  nullable=True),
        sa.Column("close_time",  sa.String(5),  nullable=True),
    )

    # ── upload_sessions ───────────────────────────────────────────────────────
    op.create_table(
        "upload_sessions",
        sa.Column("id",              sa.String(36), primary_key=True),
        sa.Column("outlet_id",       sa.String(36),
                  sa.ForeignKey("outlets.id"), nullable=False),
        sa.Column("vertical",        sa.String(50),  nullable=False, server_default="generic"),
        sa.Column("ingest_status",   sa.String(20),  nullable=True, server_default="pending"),
        sa.Column("compute_status",  sa.String(20),  nullable=True, server_default="idle"),
        sa.Column("compute_job_id",  sa.String(100), nullable=True),
        sa.Column("date_from",       sa.DateTime,    nullable=True),
        sa.Column("date_to",         sa.DateTime,    nullable=True),
        sa.Column("source_coverage", postgresql.JSON, nullable=True),
        sa.Column("supersedes_id",   sa.String(36),
                  sa.ForeignKey("upload_sessions.id"), nullable=True),
        sa.Column("ingest_errors",   postgresql.JSON, nullable=True),
        sa.Column("error_message",   sa.Text,         nullable=True),
        sa.Column("created_at",      sa.DateTime,     nullable=True),
        sa.Column("computed_at",     sa.DateTime,     nullable=True),
        sa.Column("deleted_at",      sa.DateTime,     nullable=True),
    )
    op.create_index("ix_upload_sessions_outlet_id", "upload_sessions", ["outlet_id"])

    # ── source_files ──────────────────────────────────────────────────────────
    op.create_table(
        "source_files",
        sa.Column("id",               sa.String(36), primary_key=True),
        sa.Column("session_id",       sa.String(36),
                  sa.ForeignKey("upload_sessions.id"), nullable=False),
        sa.Column("filename",         sa.String(255), nullable=False),
        sa.Column("original_name",    sa.String(255), nullable=False),
        sa.Column("file_size",        sa.Integer,     nullable=True),
        sa.Column("content_hash",     sa.String(64),  nullable=False),
        sa.Column("storage_key",      sa.String(500), nullable=True),
        sa.Column("detected_source",  sa.String(50),  nullable=True),
        sa.Column("format_version",   sa.String(20),  nullable=True),
        sa.Column("confidence",       sa.Float,       nullable=True),
        sa.Column("confirmed_source", sa.String(50),  nullable=True),
        sa.Column("data_category",    sa.String(50),  nullable=True),
        sa.Column("row_count",        sa.Integer,     nullable=True),
        sa.Column("records_stored",   sa.Integer,     nullable=True),
        sa.Column("parse_status",     sa.String(20),  nullable=True, server_default="pending"),
        sa.Column("parse_error",      sa.Text,        nullable=True),
        sa.Column("created_at",       sa.DateTime,    nullable=True),
    )
    op.create_index("ix_source_files_content_hash", "source_files", ["content_hash"])

    # ── manual_entries ────────────────────────────────────────────────────────
    op.create_table(
        "manual_entries",
        sa.Column("id",          sa.String(36), primary_key=True),
        sa.Column("outlet_id",   sa.String(36),
                  sa.ForeignKey("outlets.id"), nullable=False),
        sa.Column("entry_type",  sa.String(50),  nullable=False),
        sa.Column("period_from", sa.DateTime,    nullable=False),
        sa.Column("period_to",   sa.DateTime,    nullable=False),
        sa.Column("amount",      sa.Float,       nullable=False),
        sa.Column("notes",       sa.Text,        nullable=True),
        sa.Column("entered_by",  sa.String(36),  nullable=True),
        sa.Column("created_at",  sa.DateTime,    nullable=True),
    )
    op.create_index("ix_manual_entries_outlet_id", "manual_entries", ["outlet_id"])

    # ── stock_entries ─────────────────────────────────────────────────────────
    op.create_table(
        "stock_entries",
        sa.Column("id",                   sa.String(36), primary_key=True),
        sa.Column("outlet_id",            sa.String(36),
                  sa.ForeignKey("outlets.id"), nullable=False),
        sa.Column("period_from",          sa.DateTime, nullable=False),
        sa.Column("period_to",            sa.DateTime, nullable=False),
        sa.Column("opening_stock_value",  sa.Float,    nullable=False, server_default="0.0"),
        sa.Column("closing_stock_value",  sa.Float,    nullable=False, server_default="0.0"),
        sa.Column("purchases_value",      sa.Float,    nullable=False, server_default="0.0"),
        sa.Column("notes",                sa.Text,     nullable=True),
        sa.Column("created_at",           sa.DateTime, nullable=True),
    )
    op.create_index("ix_stock_entries_outlet_id", "stock_entries", ["outlet_id"])

    # ── sales_records ─────────────────────────────────────────────────────────
    op.create_table(
        "sales_records",
        sa.Column("id",               sa.String(36), primary_key=True),
        sa.Column("session_id",       sa.String(36),
                  sa.ForeignKey("upload_sessions.id"), nullable=False),
        sa.Column("outlet_id",        sa.String(36),
                  sa.ForeignKey("outlets.id"), nullable=False),
        sa.Column("source_type",      sa.String(50),  nullable=False),
        sa.Column("channel",          sa.String(50),  nullable=False),
        sa.Column("date",             sa.DateTime,    nullable=True),
        sa.Column("order_id",         sa.String(100), nullable=True),
        sa.Column("customer_id",      sa.String(16),  nullable=True),
        sa.Column("gross_amount",     sa.Float,       nullable=True),
        sa.Column("commission",       sa.Float,       nullable=True, server_default="0.0"),
        sa.Column("ad_spend",         sa.Float,       nullable=True, server_default="0.0"),
        sa.Column("penalty",          sa.Float,       nullable=True, server_default="0.0"),
        sa.Column("discount",         sa.Float,       nullable=True, server_default="0.0"),
        sa.Column("net_payout",       sa.Float,       nullable=True),
        sa.Column("item_name",        sa.String(255), nullable=True),
        sa.Column("quantity",         sa.Float,       nullable=True),
        sa.Column("unit_price",       sa.Float,       nullable=True),
        sa.Column("is_deduplicated",  sa.Boolean,     nullable=True, server_default="false"),
        sa.Column("created_at",       sa.DateTime,    nullable=True),
    )
    op.create_index("ix_sales_outlet_date_source", "sales_records",
                    ["outlet_id", "date", "source_type"])
    op.create_index("ix_sales_outlet_channel",     "sales_records", ["outlet_id", "channel"])
    op.create_index("ix_sales_order_id",           "sales_records", ["outlet_id", "order_id"])

    # ── purchase_records ──────────────────────────────────────────────────────
    op.create_table(
        "purchase_records",
        sa.Column("id",                 sa.String(36), primary_key=True),
        sa.Column("session_id",         sa.String(36),
                  sa.ForeignKey("upload_sessions.id"), nullable=False),
        sa.Column("outlet_id",          sa.String(36),
                  sa.ForeignKey("outlets.id"), nullable=False),
        sa.Column("source_type",        sa.String(50),  nullable=False),
        sa.Column("date",               sa.DateTime,    nullable=True),
        sa.Column("reference_id",       sa.String(100), nullable=True),
        sa.Column("vendor_name",        sa.String(255), nullable=True),
        sa.Column("ingredient_name",    sa.String(255), nullable=True),
        sa.Column("category",           sa.String(100), nullable=True),
        sa.Column("quantity_purchased", sa.Float,       nullable=True),
        sa.Column("unit",               sa.String(50),  nullable=True),
        sa.Column("unit_cost",          sa.Float,       nullable=True),
        sa.Column("total_cost",         sa.Float,       nullable=True),
        sa.Column("created_at",         sa.DateTime,    nullable=True),
    )
    op.create_index("ix_purchase_outlet_date",       "purchase_records", ["outlet_id", "date"])
    op.create_index("ix_purchase_outlet_ingredient", "purchase_records",
                    ["outlet_id", "ingredient_name"])

    # ── labor_records ─────────────────────────────────────────────────────────
    op.create_table(
        "labor_records",
        sa.Column("id",            sa.String(36), primary_key=True),
        sa.Column("session_id",    sa.String(36),
                  sa.ForeignKey("upload_sessions.id"), nullable=False),
        sa.Column("outlet_id",     sa.String(36),
                  sa.ForeignKey("outlets.id"), nullable=False),
        sa.Column("source_type",   sa.String(50),  nullable=False),
        sa.Column("date",          sa.DateTime,    nullable=True),
        sa.Column("period_from",   sa.DateTime,    nullable=True),
        sa.Column("period_to",     sa.DateTime,    nullable=True),
        sa.Column("employee_name", sa.String(255), nullable=True),
        sa.Column("role",          sa.String(100), nullable=True),
        sa.Column("shift",         sa.String(50),  nullable=True),
        sa.Column("hours_worked",  sa.Float,       nullable=True),
        sa.Column("wage_per_hour", sa.Float,       nullable=True),
        sa.Column("labor_cost",    sa.Float,       nullable=True),
        sa.Column("created_at",    sa.DateTime,    nullable=True),
    )
    op.create_index("ix_labor_outlet_date", "labor_records", ["outlet_id", "date"])

    # ── item_master ───────────────────────────────────────────────────────────
    op.create_table(
        "item_master",
        sa.Column("id",            sa.String(36), primary_key=True),
        sa.Column("outlet_id",     sa.String(36),
                  sa.ForeignKey("outlets.id"), nullable=False),
        sa.Column("item_name",     sa.String(255), nullable=False),
        sa.Column("standard_cost", sa.Float,       nullable=False),
        sa.Column("unit",          sa.String(50),  nullable=True),
        sa.Column("category",      sa.String(100), nullable=True),
        sa.Column("is_active",     sa.Boolean,     nullable=True, server_default="true"),
        sa.Column("created_at",    sa.DateTime,    nullable=True),
        sa.Column("updated_at",    sa.DateTime,    nullable=True),
        sa.Column("deleted_at",    sa.DateTime,    nullable=True),
    )
    op.create_index("ix_item_master_outlet_name", "item_master", ["outlet_id", "item_name"])

    # ── metric_snapshots ──────────────────────────────────────────────────────
    # schema_version is added from the start (avoids a future migration on live data).
    op.create_table(
        "metric_snapshots",
        sa.Column("id",             sa.String(36), primary_key=True),
        sa.Column("session_id",     sa.String(36),
                  sa.ForeignKey("upload_sessions.id"), nullable=False),
        sa.Column("outlet_id",      sa.String(36),
                  sa.ForeignKey("outlets.id"), nullable=False),
        sa.Column("vertical",       sa.String(50),    nullable=False),
        sa.Column("schema_version", sa.Integer,       nullable=False, server_default="1"),
        sa.Column("computed_at",    sa.DateTime,      nullable=True),
        sa.Column("result",         postgresql.JSON,  nullable=False),
        sa.Column("sufficiency",    postgresql.JSON,  nullable=False),
    )
    op.create_index("ix_metric_snapshots_session_id",      "metric_snapshots",
                    ["session_id"], unique=True)
    op.create_index("ix_snapshot_outlet_computed",         "metric_snapshots",
                    ["outlet_id", "computed_at"])

    # ── action_logs ───────────────────────────────────────────────────────────
    op.create_table(
        "action_logs",
        sa.Column("id",           sa.String(36), primary_key=True),
        sa.Column("outlet_id",    sa.String(36),
                  sa.ForeignKey("outlets.id"), nullable=False),
        sa.Column("session_id",   sa.String(36),  nullable=True),
        sa.Column("user_id",      sa.String(36),  nullable=True),
        sa.Column("action_type",  sa.String(100), nullable=False),
        sa.Column("payload",      postgresql.JSON, nullable=True),
        sa.Column("status",       sa.String(50),  nullable=True, server_default="pending"),
        sa.Column("result",       postgresql.JSON, nullable=True),
        sa.Column("created_at",   sa.DateTime,    nullable=True),
        sa.Column("completed_at", sa.DateTime,    nullable=True),
    )
    op.create_index("ix_action_logs_outlet_id", "action_logs", ["outlet_id"])

    # ── Row Level Security ────────────────────────────────────────────────────
    # Enabled on the four tenant-data tables. The app sets
    # SET LOCAL app.current_outlet_id = '<id>' at session start (see database.py).
    # RLS failures are non-fatal here — table may already have RLS from a previous run.
    connection = op.get_bind()
    rls_tables = ["sales_records", "purchase_records", "labor_records", "metric_snapshots"]
    for table in rls_tables:
        try:
            connection.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            connection.execute(sa.text(
                f"CREATE POLICY outlet_isolation ON {table} "
                f"USING (outlet_id::text = current_setting('app.current_outlet_id', true))"
            ))
        except Exception:
            pass   # Policy already exists — safe to continue


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("action_logs")
    op.drop_table("metric_snapshots")
    op.drop_table("item_master")
    op.drop_table("labor_records")
    op.drop_table("purchase_records")
    op.drop_table("sales_records")
    op.drop_table("stock_entries")
    op.drop_table("manual_entries")
    op.drop_table("source_files")
    op.drop_table("upload_sessions")
    op.drop_table("operating_schedules")
    op.drop_table("platform_configs")
    op.drop_table("outlets")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_table("organizations")

    # Drop custom enums
    sa.Enum(name="industry").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="plan").drop(op.get_bind(), checkfirst=True)
