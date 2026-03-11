"""
swiggy.py — Swiggy payout report parser.
Supports format versions: 2024_v1, 2023_v1, 2022_v1.
Produces SalesRecord rows (data_category: sales_aggregator).
"""
from __future__ import annotations
import pandas as pd
from app.ingestion.parsers.base import (
    BaseParser, ParseResult, find_col, safe_num, safe_date, strip_gst
)
from app.core.auth import hash_customer_id
import logging

logger = logging.getLogger(__name__)

# Column aliases per format version — most recent first
COLUMN_ALIASES = {
    "order_id":     ["order id", "orderid", "order_id", "swiggy order id"],
    "date":         ["order date", "date", "transaction date", "created at", "created_at"],
    "gross_amount": ["gross order value", "order value", "gross amount",
                     "total order value", "gross", "order total"],
    "commission":   ["commission", "commission amount", "platform commission",
                     "swiggy commission", "commission charges"],
    "ad_spend":     ["ad charges", "advertisement charges", "cpc charges",
                     "ad spend", "swiggy ads", "advertising"],
    "penalty":      ["penalty", "penalty amount", "deduction", "disputed amount",
                     "other deductions", "late dispatch penalty"],
    "discount":     ["coupon discount", "platform discount", "discount",
                     "promo discount", "offer discount", "swiggy discount"],
    "net_payout":   ["payout amount", "net payout", "settlement amount",
                     "amount paid", "net amount", "total payout"],
    "customer_id":  ["customer id", "customer_id", "user id", "user_id"],
    "item_name":    ["item name", "item", "dish name", "product"],
    "quantity":     ["quantity", "qty", "units"],
}


class SwiggyParser(BaseParser):
    source_type   = "swiggy"
    data_category = "sales_aggregator"

    def parse(self, df: pd.DataFrame, session_id: str, outlet_id: str,
              gst_rate: float = 5.0, **kwargs) -> ParseResult:

        cols = list(df.columns)
        m = {field: find_col(cols, aliases) for field, aliases in COLUMN_ALIASES.items()}

        # Warn about unknown format if key columns not found
        warnings = []
        if not m.get("gross_amount"):
            warnings.append("Could not find gross amount column — check Swiggy export format.")
        if not m.get("net_payout"):
            warnings.append("Could not find net payout column.")

        records = []
        errors  = []

        for idx, row in df.iterrows():
            try:
                gross_raw = float(safe_num(pd.Series([row[m["gross_amount"]]]))[0]) if m["gross_amount"] else 0.0
                gross     = strip_gst(gross_raw, gst_rate)

                rec = self._base_record(session_id, outlet_id)
                rec.update({
                    "channel":      "swiggy",
                    "date":         safe_date(pd.Series([row[m["date"]]]))[0] if m["date"] else None,
                    "order_id":     str(row[m["order_id"]])[:100] if m["order_id"] else None,
                    "customer_id":  hash_customer_id(
                                        str(row[m["customer_id"]]) if m["customer_id"] else "",
                                        outlet_id
                                    ),
                    "gross_amount": gross,
                    "commission":   float(safe_num(pd.Series([row[m["commission"]]]))[0]) if m["commission"] else 0.0,
                    "ad_spend":     float(safe_num(pd.Series([row[m["ad_spend"]]]))[0])   if m["ad_spend"]   else 0.0,
                    "penalty":      float(safe_num(pd.Series([row[m["penalty"]]]))[0])    if m["penalty"]    else 0.0,
                    "discount":     float(safe_num(pd.Series([row[m["discount"]]]))[0])   if m["discount"]   else 0.0,
                    "net_payout":   float(safe_num(pd.Series([row[m["net_payout"]]]))[0]) if m["net_payout"] else None,
                    "item_name":    str(row[m["item_name"]]) if m["item_name"] else None,
                    "quantity":     float(safe_num(pd.Series([row[m["quantity"]]]))[0])   if m["quantity"]   else None,
                    "is_deduplicated": False,
                })
                records.append(rec)
            except Exception as e:
                errors.append(f"Row {idx}: {e}")
                if len(errors) > 20:
                    errors.append("Too many errors — truncated.")
                    break

        return ParseResult(
            source_type   = self.source_type,
            data_category = self.data_category,
            records       = records,
            row_count     = len(df),
            parse_errors  = errors,
            warnings      = warnings,
        )
