"""
tests/unit/test_fingerprint.py — Unit tests for source detection.

fingerprint.detect_source() is the most critical classification logic.
A wrong detection means the wrong parser runs and all metrics are wrong.
These tests cover:
  - Correct classification of Swiggy, Zomato, Petpooja headers
  - Confidence scores above and below the confirm threshold
  - Ambiguous / unknown files returning needs_confirm=True
  - data_category assignment is correct per source
"""
import pytest
import pandas as pd
from app.ingestion.fingerprint import detect_source, SourceDetection


def _make_df(columns: list[str], n_rows: int = 5) -> pd.DataFrame:
    """Helper: build a DataFrame with the given columns and dummy data."""
    return pd.DataFrame({c: [f"val_{i}" for i in range(n_rows)] for c in columns})


# ── Swiggy ────────────────────────────────────────────────────────────────────

class TestSwiggyDetection:

    def test_swiggy_standard_headers_detected(self):
        """Standard 2024 Swiggy export should be detected with high confidence."""
        df = _make_df([
            "order id", "order date", "gross order value",
            "commission", "ad charges", "penalty",
            "coupon discount", "payout amount", "customer id", "restaurant id"
        ])
        result = detect_source(list(df.columns), df)
        assert result.source_type   == "swiggy"
        assert result.data_category == "sales_aggregator"
        assert result.confidence    >= 0.70
        assert result.needs_confirm is False

    def test_swiggy_minimal_required_columns(self):
        """Only required Swiggy columns — should still detect but with lower confidence."""
        df = _make_df(["order id", "payout amount", "commission"])
        result = detect_source(list(df.columns), df)
        assert result.source_type == "swiggy"

    def test_swiggy_confidence_above_threshold(self):
        """Full Swiggy header set should be COMPLETE confidence (no confirm needed)."""
        df = _make_df([
            "order id", "order date", "gross order value", "commission",
            "ad charges", "penalty", "coupon discount", "payout amount",
            "customer id", "restaurant id", "order status", "cancelled"
        ])
        result = detect_source(list(df.columns), df)
        assert result.confidence >= 0.85
        assert result.needs_confirm is False


# ── Zomato ────────────────────────────────────────────────────────────────────

class TestZomatoDetection:

    def test_zomato_standard_headers_detected(self):
        df = _make_df([
            "order_id", "order_date", "order_total", "platform_fee",
            "zomato_ads", "cancellation_charges", "discount",
            "net_payout", "customer_id", "res_id"
        ])
        result = detect_source(list(df.columns), df)
        assert result.source_type   == "zomato"
        assert result.data_category == "sales_aggregator"
        assert result.confidence    >= 0.70

    def test_zomato_required_columns_only(self):
        df = _make_df(["order_id", "net_payout", "platform_fee"])
        result = detect_source(list(df.columns), df)
        assert result.source_type == "zomato"

    def test_zomato_not_confused_with_swiggy(self):
        """Zomato-specific columns should not be confused with Swiggy."""
        df = _make_df(["order_id", "net_payout", "platform_fee", "zomato_ads", "res_id"])
        result = detect_source(list(df.columns), df)
        assert result.source_type == "zomato"
        assert result.source_type != "swiggy"


# ── Petpooja ──────────────────────────────────────────────────────────────────

class TestPetpoojaDetection:

    def test_petpooja_pos_headers_detected(self):
        df = _make_df([
            "bill no", "date", "item name", "qty", "rate",
            "sub total", "cgst", "sgst", "total", "table", "waiter", "kot"
        ])
        result = detect_source(list(df.columns), df)
        assert result.source_type   == "petpooja"
        assert result.data_category == "sales_pos"
        assert result.confidence    >= 0.70

    def test_petpooja_required_columns(self):
        df = _make_df(["bill no", "item name", "qty"])
        result = detect_source(list(df.columns), df)
        assert result.source_type == "petpooja"


# ── Ambiguous / unknown ───────────────────────────────────────────────────────

class TestAmbiguousDetection:

    def test_random_columns_return_generic(self):
        """Columns with no matching signatures should fall back to generic."""
        df = _make_df(["column_a", "column_b", "column_c", "amount", "date"])
        result = detect_source(list(df.columns), df)
        assert result.source_type   == "generic"
        assert result.needs_confirm is True

    def test_low_confidence_sets_needs_confirm(self):
        """Any detection with confidence < 0.70 must set needs_confirm=True."""
        # Use only 1 weak signal column
        df = _make_df(["order id", "amount", "date"])
        result = detect_source(list(df.columns), df)
        if result.confidence < 0.70:
            assert result.needs_confirm is True

    def test_empty_dataframe_returns_generic(self):
        """Empty DataFrame should not crash — returns generic with low confidence."""
        df = pd.DataFrame()
        result = detect_source([], df)
        assert result.source_type == "generic"
        assert result.needs_confirm is True

    def test_tally_columns_detected(self):
        """Basic Tally purchase columns should be detected."""
        df = _make_df(["voucher no", "date", "party name", "ledger", "debit", "credit"])
        result = detect_source(list(df.columns), df)
        # Should at least be tally or generic — not swiggy/zomato/petpooja
        assert result.source_type not in ("swiggy", "zomato", "petpooja")
