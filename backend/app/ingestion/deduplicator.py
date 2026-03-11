"""
deduplicator.py — Cross-source deduplication strategy.

Problem: A restaurant using Petpooja for all orders (including delivery)
will have the same Swiggy/Zomato order in BOTH the POS export AND the
aggregator payout CSV. Summing across both double-counts revenue.

Strategy (explicit per use-case):
  True Net Yield / AOV / Dependency  → aggregator source wins for online channels
  Item-level analysis                → POS source wins (aggregators lack item detail)
  Dine-in revenue                    → POS source only (no aggregator data)

Implementation:
  After all records are stored, mark POS records for online channels
  as is_deduplicated=True if a matching aggregator record exists for
  the same order_id.
"""
from __future__ import annotations
import logging
from typing import List
import pandas as pd

logger = logging.getLogger(__name__)


def deduplicate_sales(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a combined sales DataFrame with columns:
      [id, order_id, channel, source_type, gross_amount, is_deduplicated, ...]

    Marks POS rows for online channels (swiggy/zomato) as deduplicated
    when a matching aggregator row exists for the same order_id.

    Returns the DataFrame with is_deduplicated updated.
    Aggregator rows always win — they have commission/penalty/net_payout detail.
    """
    if sales_df.empty:
        return sales_df

    df = sales_df.copy()
    df["is_deduplicated"] = False

    # Get order_ids that exist in aggregator sources
    aggregator_order_ids = set(
        df[
            (df["source_type"].isin(["swiggy", "zomato"])) &
            (df["order_id"].notna()) &
            (df["order_id"] != "")
        ]["order_id"].tolist()
    )

    if not aggregator_order_ids:
        return df   # no aggregator data → no dedup needed

    # Mark POS rows for online channels where order_id matches an aggregator row
    pos_online_mask = (
        (df["source_type"] == "petpooja") &
        (df["channel"].isin(["swiggy", "zomato"])) &
        (df["order_id"].isin(aggregator_order_ids))
    )

    dedup_count = pos_online_mask.sum()
    if dedup_count > 0:
        df.loc[pos_online_mask, "is_deduplicated"] = True
        logger.info(
            f"Deduplicated {dedup_count} POS rows — aggregator records take precedence "
            f"for {len(aggregator_order_ids)} online orders."
        )

    return df


def get_revenue_df(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns sales records appropriate for revenue metrics (Net Yield, AOV, Dependency).
    Excludes deduplicated rows.
    For channels with both aggregator and POS data, aggregator rows are used.
    """
    return sales_df[~sales_df["is_deduplicated"]].copy()


def get_item_df(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns sales records appropriate for item-level analysis (inventory variance).
    Uses POS source preferentially — it has item names and quantities.
    Excludes aggregator rows if POS rows exist for the same channel.
    """
    pos_rows  = sales_df[sales_df["source_type"] == "petpooja"]
    if not pos_rows.empty:
        return pos_rows.copy()
    # Fall back to all rows if no POS data
    return sales_df.copy()
