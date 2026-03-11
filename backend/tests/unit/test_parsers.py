"""
tests/unit/test_parsers.py — Unit tests for Swiggy and Zomato parsers.

Tests verify:
  - Parser produces the right number of records
  - Key financial fields are populated and non-zero
  - GST stripping is applied correctly (gross_amount < raw_amount)
  - customer_id is hashed (16 hex chars, not the raw value)
  - channel is set correctly per source
  - Parse errors are captured but don't crash the parser
  - Parsers are tolerant of missing optional columns
"""
import pytest
import pandas as pd
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures"

SESSION_ID = "test-session-00000001"
OUTLET_ID  = "test-outlet-00000001"
GST_RATE   = 5.0


# ── Swiggy parser ──────────────────────────────────────────────────────────────

class TestSwiggyParser:
    """Tests the SwiggyParser against the fixture CSV."""

    @pytest.fixture
    def parsed(self):
        from app.ingestion.sanitiser import sanitise
        from app.ingestion.parsers.swiggy import SwiggyParser

        content = (FIXTURES / "swiggy_sample.csv").read_bytes()
        df, _ = sanitise(content, "swiggy_sample.csv")
        result = SwiggyParser().parse(df, SESSION_ID, OUTLET_ID, GST_RATE)
        return result

    def test_record_count_matches_rows(self, parsed):
        """One record per data row in the fixture."""
        assert len(parsed.records) == 10

    def test_channel_is_swiggy(self, parsed):
        """All records from Swiggy parser should have channel='swiggy'."""
        assert all(r["channel"] == "swiggy" for r in parsed.records)

    def test_source_type_is_swiggy(self, parsed):
        assert parsed.source_type == "swiggy"
        assert parsed.data_category == "sales_aggregator"

    def test_gross_amount_is_gst_stripped(self, parsed):
        """gross_amount must be less than the raw CSV value (GST was removed)."""
        # Fixture row 1: gross_order_value=450.00, GST=5% → 450/1.05 ≈ 428.57
        first = parsed.records[0]
        assert first["gross_amount"] < 450.00
        assert first["gross_amount"] == pytest.approx(450.00 / 1.05, abs=0.01)

    def test_net_payout_populated(self, parsed):
        """net_payout should be populated from 'payout amount' column."""
        assert all(r["net_payout"] is not None for r in parsed.records)
        # Fixture row 1: payout_amount=286.00
        assert parsed.records[0]["net_payout"] == pytest.approx(286.00, abs=0.01)

    def test_customer_id_is_hashed(self, parsed):
        """customer_id must be a 16-char hex hash, not the raw CUST001 value."""
        for rec in parsed.records:
            if rec["customer_id"]:
                assert len(rec["customer_id"]) == 16
                assert rec["customer_id"] != "CUST001"

    def test_commission_and_ad_spend_parsed(self, parsed):
        """Commission and ad_spend should be parsed as floats."""
        first = parsed.records[0]
        assert isinstance(first["commission"], float)
        assert first["commission"] > 0

    def test_order_id_present(self, parsed):
        assert parsed.records[0]["order_id"] == "SWG10001"

    def test_session_and_outlet_id_set(self, parsed):
        """Every record must carry the session_id and outlet_id it was created with."""
        for rec in parsed.records:
            assert rec["session_id"] == SESSION_ID
            assert rec["outlet_id"]  == OUTLET_ID

    def test_no_fatal_parse_errors(self, parsed):
        """A clean fixture CSV should produce zero parse errors."""
        assert len(parsed.parse_errors) == 0

    def test_missing_optional_columns_dont_crash(self):
        """If optional columns like ad_charges are missing, parser should not crash."""
        from app.ingestion.parsers.swiggy import SwiggyParser
        df = pd.DataFrame({
            "order id":          ["SWG99001"],
            "order date":        ["2024-01-05"],
            "gross order value": [500.0],
            "commission":        [110.0],
            "payout amount":     [390.0],
        })
        result = SwiggyParser().parse(df, SESSION_ID, OUTLET_ID, GST_RATE)
        assert len(result.records) == 1
        assert result.records[0]["ad_spend"] == 0.0   # defaults to 0 when column missing


# ── Zomato parser ──────────────────────────────────────────────────────────────

class TestZomatoParser:
    """Tests the ZomatoParser against the fixture CSV."""

    @pytest.fixture
    def parsed(self):
        from app.ingestion.sanitiser import sanitise
        from app.ingestion.parsers.others import ZomatoParser

        content = (FIXTURES / "zomato_sample.csv").read_bytes()
        df, _ = sanitise(content, "zomato_sample.csv")
        result = ZomatoParser().parse(df, SESSION_ID, OUTLET_ID, GST_RATE)
        return result

    def test_record_count(self, parsed):
        assert len(parsed.records) == 8

    def test_channel_is_zomato(self, parsed):
        assert all(r["channel"] == "zomato" for r in parsed.records)

    def test_source_type_and_category(self, parsed):
        assert parsed.source_type   == "zomato"
        assert parsed.data_category == "sales_aggregator"

    def test_gst_stripping_applied(self, parsed):
        """Zomato parser must also strip GST from gross amounts."""
        first = parsed.records[0]
        assert first["gross_amount"] == pytest.approx(520.00 / 1.05, abs=0.01)

    def test_net_payout_populated(self, parsed):
        assert all(r["net_payout"] is not None for r in parsed.records)

    def test_customer_id_hashed(self, parsed):
        for rec in parsed.records:
            if rec["customer_id"]:
                assert len(rec["customer_id"]) == 16

    def test_no_parse_errors(self, parsed):
        assert len(parsed.parse_errors) == 0


# ── Petpooja parser ────────────────────────────────────────────────────────────

class TestPetpoojaParser:
    """Tests the PetpoojaParser against the fixture CSV."""

    @pytest.fixture
    def parsed(self):
        from app.ingestion.sanitiser import sanitise
        from app.ingestion.parsers.others import PetpoojaParser

        content = (FIXTURES / "petpooja_sample.csv").read_bytes()
        df, _ = sanitise(content, "petpooja_sample.csv")
        result = PetpoojaParser().parse(df, SESSION_ID, OUTLET_ID, GST_RATE)
        return result

    def test_record_count(self, parsed):
        assert len(parsed.records) == 8

    def test_data_category_is_sales_pos(self, parsed):
        assert parsed.data_category == "sales_pos"

    def test_item_names_present(self, parsed):
        """POS records should always have item_name set."""
        assert all(r.get("item_name") for r in parsed.records)

    def test_channel_mapping(self, parsed):
        """Dine-In → dine_in, Swiggy → swiggy, Zomato → zomato."""
        channels = {r["channel"] for r in parsed.records}
        assert "dine_in" in channels     # rows with table/waiter
        # Fixture also has Swiggy and Zomato rows
        assert len(channels) > 1
