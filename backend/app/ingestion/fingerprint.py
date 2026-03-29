"""
fingerprint.py — Two-signal source detection: column names + data content sampling.
Also detects format version (aggregators change their export formats periodically).

Returns: SourceDetection(source_type, data_category, confidence, format_version, needs_confirm)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import re
import pandas as pd


@dataclass
class SourceDetection:
    source_type:   str    # swiggy|zomato|petpooja|tally|payroll|generic
    data_category: str    # sales_aggregator|sales_pos|purchases|labor|generic
    confidence:    float  # 0.0 – 1.0
    format_version:str    # e.g. "2024_v1" | "unknown"
    needs_confirm: bool   # True if confidence < 0.70


# ── Column-name signatures ────────────────────────────────────────────────────

COLUMN_SIGNATURES = {
    "swiggy": {
        "required": ["order id", "payout amount", "commission"],
        "bonus":    ["ad charges", "penalty", "restaurant id", "coupon discount",
                     "delivery charge", "net payout", "order status", "cancelled"],
    },
    "zomato": {
        "required": ["order_id", "net_payout", "platform_fee"],
        "bonus":    ["zomato_ads", "res_id", "rider tip", "cancellation charges",
                     "settlement", "payment mode"],
    },
    "petpooja": {
        "required": ["bill no", "item name", "qty"],
        "bonus":    ["table", "waiter", "kot", "cgst", "sgst", "category",
                     "sub total", "petpooja", "discount amount"],
    },
    "tally": {
        "required": ["voucher date", "party name", "amount"],
        "bonus":    ["stock item", "ledger", "narration", "voucher type",
                     "godown", "batch", "closing balance", "tally"],
    },
    "payroll": {
        "required": ["employee", "salary"],           # "wage" rarely appears; "salary" is universal
        "bonus":    ["shift", "attendance", "basic salary", "gross salary", "net salary",
                     "pf", "esi", "tds", "working days", "days present", "overtime",
                     "designation", "department", "allowance", "deduction",
                     "wage", "net pay", "basic pay", "hra"],
    },
}

DATA_CATEGORY_MAP = {
    "swiggy":   "sales_aggregator",
    "zomato":   "sales_aggregator",
    "petpooja": "sales_pos",
    "tally":    "purchases",
    "payroll":  "labor",
    "generic":  "generic",
}

# ── Format version fingerprints ───────────────────────────────────────────────
# Each platform changes column names periodically — track known versions.

SWIGGY_VERSIONS = {
    "2024_v1": ["order id", "order date", "gross order value", "commission",
                "ad charges", "payout amount"],
    "2023_v1": ["order id", "order date", "order value", "platform commission",
                "advertisement charges", "net payout"],
    "2022_v1": ["orderid", "date", "gross", "commission", "ads", "payout"],
}

ZOMATO_VERSIONS = {
    "2024_v1": ["order_id", "order_date", "order_total", "platform_fee",
                "zomato_ads", "net_payout"],
    "2023_v1": ["order_id", "created_at", "subtotal", "commission",
                "advertisement", "payout"],
}

PETPOOJA_VERSIONS = {
    "2024_v1": ["bill no", "bill date", "item name", "qty", "rate",
                "cgst", "sgst", "total"],
    "2023_v1": ["bill no", "date", "item name", "quantity", "price",
                "tax", "grand total"],
}

PAYROLL_VERSIONS = {
    "standard_v1": ["employee id", "employee name", "role", "basic salary",
                    "gross salary", "net salary", "pf deduction"],
    "generic_v1":  ["employee name", "salary", "attendance", "working days"],
}

VERSION_MAPS = {
    "swiggy":   SWIGGY_VERSIONS,
    "zomato":   ZOMATO_VERSIONS,
    "petpooja": PETPOOJA_VERSIONS,
    "payroll":  PAYROLL_VERSIONS,
}


def _normalise_headers(headers: List[str]) -> List[str]:
    return [re.sub(r"\s+", " ", h.lower().strip()) for h in headers]


def _column_score(norm_headers: List[str], required: List[str], bonus: List[str]) -> float:
    def matches(kw): return any(kw in h for h in norm_headers)
    req_hits = sum(1 for k in required if matches(k))
    bon_hits = sum(1 for k in bonus   if matches(k))
    req_score = req_hits / len(required) if required else 0.0
    bon_score = bon_hits / len(bonus)    if bonus    else 0.0
    return round(req_score * 0.70 + bon_score * 0.30, 4)


# ── Content signal detection ──────────────────────────────────────────────────

def _content_signals(df: pd.DataFrame) -> dict:
    """
    Sample data content to infer domain signals beyond column names.
    Returns dict of detected signals.
    """
    signals = {}
    joined_sample = " ".join(
        df.head(20).astype(str).values.flatten().tolist()
    ).lower()

    # Platform name mentions in data values
    if "swiggy" in joined_sample:     signals["mentions_swiggy"] = True
    if "zomato" in joined_sample:     signals["mentions_zomato"] = True
    if "petpooja" in joined_sample:   signals["mentions_petpooja"] = True
    if "tally" in joined_sample:      signals["mentions_tally"] = True

    # GST rate patterns (5%, 12%, 18%) — indicates Indian tax document
    import re
    gst_pattern = r'\b(5|12|18|28)\.0*%?\b'
    if re.search(gst_pattern, joined_sample):
        signals["has_gst_rates"] = True

    # INR currency symbols
    if "₹" in joined_sample or "inr" in joined_sample:
        signals["has_inr"] = True

    # Ingredient-like values (food categories)
    food_keywords = ["paneer", "chicken", "oil", "rice", "flour", "dal",
                     "onion", "tomato", "masala", "ghee", "milk"]
    if any(k in joined_sample for k in food_keywords):
        signals["has_ingredients"] = True

    # Employee role keywords
    staff_keywords = ["chef", "waiter", "manager", "cashier", "helper", "captain"]
    if any(k in joined_sample for k in staff_keywords):
        signals["has_staff_roles"] = True

    return signals


def _detect_format_version(norm_headers: List[str], source_type: str) -> str:
    """Match headers against known format versions for this source type."""
    versions = VERSION_MAPS.get(source_type, {})
    best_version = "unknown"
    best_score = 0.0
    for version, version_headers in versions.items():
        hits = sum(1 for h in version_headers if any(h in nh for nh in norm_headers))
        score = hits / len(version_headers)
        if score > best_score:
            best_score = score
            best_version = version
    return best_version if best_score >= 0.5 else "unknown"


# ── Main detection function ───────────────────────────────────────────────────

def detect_source(headers: List[str], df: pd.DataFrame = None) -> SourceDetection:
    """
    Two-signal detection: column names + content sampling.
    Returns SourceDetection with source type, category, confidence, format version.
    """
    norm = _normalise_headers(headers)
    joined = " ".join(norm)

    # Strong platform name signal in headers — override everything
    if "swiggy" in joined:
        return SourceDetection("swiggy", "sales_aggregator", 0.97,
                               _detect_format_version(norm, "swiggy"), False)
    if "zomato" in joined:
        return SourceDetection("zomato", "sales_aggregator", 0.97,
                               _detect_format_version(norm, "zomato"), False)
    if "petpooja" in joined or "kot" in joined:
        return SourceDetection("petpooja", "sales_pos", 0.95,
                               _detect_format_version(norm, "petpooja"), False)
    if "tally" in joined:
        return SourceDetection("tally", "purchases", 0.95, "unknown", False)

    # Score all signatures
    scores = []
    for source, sig in COLUMN_SIGNATURES.items():
        score = _column_score(norm, sig["required"], sig["bonus"])
        scores.append((source, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    best_source, best_score = scores[0]

    # Apply content signal boost
    if df is not None:
        signals = _content_signals(df)
        if signals.get("mentions_swiggy"):    best_source, best_score = "swiggy", min(1.0, best_score + 0.2)
        if signals.get("mentions_zomato"):    best_source, best_score = "zomato", min(1.0, best_score + 0.2)
        if signals.get("has_ingredients"):    best_score = min(1.0, best_score + 0.1)
        if signals.get("has_staff_roles"):
            # Boost payroll score regardless of current best — staff role keywords
            # are strong payroll signals (chef, waiter, manager, cashier, captain)
            payroll_score = next((s for src, s in scores if src == "payroll"), 0)
            if payroll_score + 0.20 > best_score:
                best_source = "payroll"
                best_score  = min(1.0, payroll_score + 0.20)
            elif best_source == "payroll":
                best_score  = min(1.0, best_score + 0.15)
        if signals.get("has_gst_rates"):      best_score = min(1.0, best_score + 0.05)

    if best_score < 0.30:
        best_source = "generic"

    category       = DATA_CATEGORY_MAP.get(best_source, "generic")
    format_version = _detect_format_version(norm, best_source)
    needs_confirm  = best_score < 0.70 or format_version == "unknown"

    return SourceDetection(
        source_type    = best_source,
        data_category  = category,
        confidence     = round(best_score, 3),
        format_version = format_version,
        needs_confirm  = needs_confirm,
    )


def detect_all(files: List[tuple]) -> List[dict]:
    """
    Detect sources for a list of (filename, headers, df) tuples.
    """
    return [
        {
            "filename":      fname,
            "detection":     detect_source(headers, df),
        }
        for fname, headers, df in files
    ]
