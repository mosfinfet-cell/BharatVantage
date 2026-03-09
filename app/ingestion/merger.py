"""
merger.py — Assembles metric-specific DataFrames from stored domain records.

Each metric needs different combinations of sales/purchase/labor data.
The merger is the single place that knows which tables feed which metrics.
Also validates date range alignment across sources and flags mismatches.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

logger = logging.getLogger(__name__)


@dataclass
class MetricFrames:
    """All DataFrames needed by the restaurant metric engine."""

    # Revenue data — deduped, ex-GST
    revenue_df:         pd.DataFrame = field(default_factory=pd.DataFrame)

    # Full sales data including POS rows (for item-level analysis)
    item_sales_df:      pd.DataFrame = field(default_factory=pd.DataFrame)

    # Purchase/COGS data from Tally/vendor invoices
    purchase_df:        pd.DataFrame = field(default_factory=pd.DataFrame)

    # Labor/payroll data
    labor_df:           pd.DataFrame = field(default_factory=pd.DataFrame)

    # Source coverage metadata
    sources_present:    List[str] = field(default_factory=list)
    date_from:          Optional[datetime] = None
    date_to:            Optional[datetime] = None

    # Date range alignment warnings
    alignment_warnings: List[str] = field(default_factory=list)

    def has_source(self, source: str) -> bool:
        return source in self.sources_present

    def has_any(self, *sources: str) -> bool:
        return any(s in self.sources_present for s in sources)


async def build_metric_frames(
    db:         AsyncSession,
    session_id: str,
    outlet_id:  str,
) -> MetricFrames:
    """
    Load all domain records for a session and assemble MetricFrames.
    Handles date range alignment checking and deduplication.
    """
    frames = MetricFrames()

    # ── Load sales records ─────────────────────────────────────────────────
    sales_result = await db.execute(
        text("""
            SELECT id, source_type, channel, date, order_id, customer_id,
                   gross_amount, commission, ad_spend, penalty, discount,
                   net_payout, item_name, quantity, unit_price, is_deduplicated
            FROM sales_records
            WHERE session_id = :sid AND outlet_id = :oid
            ORDER BY date
        """),
        {"sid": session_id, "oid": outlet_id}
    )
    sales_rows = sales_result.fetchall()

    if sales_rows:
        sales_df = pd.DataFrame(sales_rows, columns=sales_result.keys())
        sales_df["date"] = pd.to_datetime(sales_df["date"], errors="coerce")

        # Apply deduplication
        from app.ingestion.deduplicator import deduplicate_sales, get_revenue_df, get_item_df
        sales_df = deduplicate_sales(sales_df)
        frames.revenue_df   = get_revenue_df(sales_df)
        frames.item_sales_df= get_item_df(sales_df)
        frames.sources_present.extend(
            sales_df["source_type"].unique().tolist()
        )

    # ── Load purchase records ──────────────────────────────────────────────
    purchase_result = await db.execute(
        text("""
            SELECT id, source_type, date, reference_id, vendor_name,
                   ingredient_name, category, quantity_purchased,
                   unit, unit_cost, total_cost
            FROM purchase_records
            WHERE session_id = :sid AND outlet_id = :oid
            ORDER BY date
        """),
        {"sid": session_id, "oid": outlet_id}
    )
    purchase_rows = purchase_result.fetchall()

    if purchase_rows:
        frames.purchase_df = pd.DataFrame(purchase_rows, columns=purchase_result.keys())
        frames.purchase_df["date"] = pd.to_datetime(frames.purchase_df["date"], errors="coerce")
        if "tally" not in frames.sources_present:
            frames.sources_present.append("tally")

    # ── Load labor records ─────────────────────────────────────────────────
    labor_result = await db.execute(
        text("""
            SELECT id, source_type, date, period_from, period_to,
                   employee_name, role, shift, hours_worked,
                   wage_per_hour, labor_cost
            FROM labor_records
            WHERE session_id = :sid AND outlet_id = :oid
            ORDER BY date
        """),
        {"sid": session_id, "oid": outlet_id}
    )
    labor_rows = labor_result.fetchall()

    if labor_rows:
        frames.labor_df = pd.DataFrame(labor_rows, columns=labor_result.keys())
        frames.labor_df["date"] = pd.to_datetime(frames.labor_df["date"], errors="coerce")
        if "payroll" not in frames.sources_present:
            frames.sources_present.append("payroll")

    # ── Date range and alignment ───────────────────────────────────────────
    frames.date_from, frames.date_to = _compute_intersection_range(frames)
    frames.alignment_warnings        = _check_alignment(frames)

    logger.info(
        f"MetricFrames built for session {session_id}: "
        f"sources={frames.sources_present}, "
        f"range={frames.date_from} → {frames.date_to}, "
        f"warnings={len(frames.alignment_warnings)}"
    )

    return frames


def _compute_intersection_range(frames: MetricFrames):
    """
    Compute the intersection date range across all sources.
    This is the 'safe' range where all data is available.
    """
    ranges = []

    for df in [frames.revenue_df, frames.purchase_df, frames.labor_df]:
        if df.empty: continue
        dated = df[df["date"].notna()]
        if dated.empty: continue
        ranges.append((dated["date"].min(), dated["date"].max()))

    if not ranges:
        return None, None

    # Intersection: latest start, earliest end
    date_from = max(r[0] for r in ranges)
    date_to   = min(r[1] for r in ranges)

    if date_from > date_to:
        # No intersection — return union instead and flag warning
        date_from = min(r[0] for r in ranges)
        date_to   = max(r[1] for r in ranges)

    return date_from, date_to


def _check_alignment(frames: MetricFrames) -> List[str]:
    """
    Check for date range mismatches between sources that would
    produce wrong metric calculations.
    """
    warnings = []
    source_ranges = {}

    for name, df in [
        ("sales",     frames.revenue_df),
        ("purchases", frames.purchase_df),
        ("labor",     frames.labor_df),
    ]:
        if df.empty: continue
        dated = df[df["date"].notna()]
        if dated.empty: continue
        source_ranges[name] = (dated["date"].min(), dated["date"].max())

    if len(source_ranges) < 2:
        return warnings

    # Check if any source range deviates significantly from others
    all_starts = [r[0] for r in source_ranges.values()]
    all_ends   = [r[1] for r in source_ranges.values()]

    start_spread = (max(all_starts) - min(all_starts)).days
    end_spread   = (max(all_ends)   - min(all_ends)).days

    if start_spread > 7:
        warnings.append(
            f"Source date ranges don't align at start (±{start_spread} days). "
            f"Prime Cost may be inaccurate — ensure all files cover the same period."
        )
    if end_spread > 7:
        warnings.append(
            f"Source date ranges don't align at end (±{end_spread} days). "
            f"Metrics computed over the intersection period only."
        )

    return warnings
