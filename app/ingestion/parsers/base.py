"""
base.py — Abstract base parser. All source parsers inherit from this.

Each parser:
1. Receives a sanitised DataFrame
2. Maps columns to normalised domain fields
3. Returns domain-specific records (SalesRecord, PurchaseRecord, LaborRecord)
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import pandas as pd
import numpy as np
import re
import logging
from datetime import datetime, timezone
import pytz

IST = pytz.timezone("Asia/Kolkata")
logger = logging.getLogger(__name__)


# ── Shared helpers ─────────────────────────────────────────────────────────────

def find_col(df_cols: List[str], aliases: List[str]) -> Optional[str]:
    """Find the first df column whose normalised name matches any alias substring."""
    norm = {re.sub(r"\s+", " ", c.lower().strip()): c for c in df_cols}
    for alias in aliases:
        if alias in norm:
            return norm[alias]
    # Substring fallback
    for alias in aliases:
        for nc, orig in norm.items():
            if alias in nc:
                return orig
    return None


def safe_num(series: pd.Series) -> pd.Series:
    """Coerce to float, stripping ₹ symbols, commas, and whitespace."""
    cleaned = series.astype(str).str.replace(r"[₹,\s]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0)


def safe_date(series: pd.Series) -> pd.Series:
    """Parse dates, normalise to IST timezone-aware datetimes."""
    parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    # Localise naive datetimes to IST
    def localise(dt):
        if pd.isna(dt):
            return None
        if dt.tzinfo is None:
            return IST.localize(dt)
        return dt.astimezone(IST)
    return parsed.apply(localise)


def strip_gst(amount: float, gst_rate: float) -> float:
    """Remove embedded GST from an inclusive amount."""
    if gst_rate <= 0:
        return amount
    return round(amount / (1 + gst_rate / 100), 2)


@dataclass
class ParseResult:
    """Output of a parser run."""
    source_type:    str
    data_category:  str
    records:        List[dict]        # list of dicts ready for DB model
    row_count:      int
    parse_errors:   List[str] = field(default_factory=list)
    warnings:       List[str] = field(default_factory=list)


class BaseParser(ABC):
    """
    Abstract parser. Subclasses implement:
    - source_type: str
    - data_category: str
    - parse(df, session_id, outlet_id, gst_rate, **kwargs) -> ParseResult
    """
    source_type:   str = "generic"
    data_category: str = "generic"

    @abstractmethod
    def parse(
        self,
        df:         pd.DataFrame,
        session_id: str,
        outlet_id:  str,
        gst_rate:   float = 5.0,
        **kwargs,
    ) -> ParseResult:
        pass

    def _base_record(self, session_id: str, outlet_id: str) -> dict:
        return {
            "session_id":  session_id,
            "outlet_id":   outlet_id,
            "source_type": self.source_type,
            "created_at":  datetime.utcnow(),
        }
