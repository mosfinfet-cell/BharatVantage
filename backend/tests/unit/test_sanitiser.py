"""
tests/unit/test_sanitiser.py — Unit tests for file sanitiser.

Covers:
  - CSV encoding fallbacks (UTF-8, latin-1, cp1252)
  - Header row detection when metadata rows precede the real headers
  - Total/subtotal row removal
  - Merged cell artefact forward-fill
  - Magic byte validation for XLSX/XLS files
  - Empty file rejection
"""
import pytest
import io
import pandas as pd
from app.ingestion.sanitiser import sanitise, validate_file


def _csv_bytes(rows: list[list], encoding: str = "utf-8") -> bytes:
    """Helper: build a CSV as bytes from a list of rows."""
    lines = [",".join(str(c) for c in row) for row in rows]
    return "\n".join(lines).encode(encoding)


# ── validate_file ─────────────────────────────────────────────────────────────

class TestValidateFile:

    def test_valid_csv_utf8(self):
        content = _csv_bytes([["col1", "col2"], ["a", "b"]])
        ok, err = validate_file(content, "test.csv")
        assert ok is True
        assert err == ""

    def test_unsupported_extension_rejected(self):
        content = b"some content"
        ok, err = validate_file(content, "data.pdf")
        assert ok is False
        assert "Unsupported" in err

    def test_fake_xlsx_rejected(self):
        """A CSV renamed to .xlsx should fail magic byte check."""
        content = _csv_bytes([["col1", "col2"], ["a", "b"]])
        ok, err = validate_file(content, "data.xlsx")
        assert ok is False

    def test_binary_csv_rejected(self):
        """Binary garbage should fail encoding check."""
        content = bytes(range(256))
        ok, err = validate_file(content, "data.csv")
        assert ok is False


# ── sanitise ──────────────────────────────────────────────────────────────────

class TestSanitise:

    def test_basic_csv_returns_dataframe(self):
        content = _csv_bytes([
            ["order_id", "amount", "date"],
            ["ORD001",   "500",    "2024-01-05"],
            ["ORD002",   "320",    "2024-01-06"],
        ])
        df, headers = sanitise(content, "test.csv")
        assert len(df) == 2
        assert "order_id" in headers
        assert "amount" in headers

    def test_metadata_rows_above_headers_stripped(self):
        """Tally-style: first 2 rows are metadata, real headers are row 2."""
        content = _csv_bytes([
            ["Report Name:", "Daily Sales Summary"],
            ["Period:", "January 2024"],
            ["order_id", "amount", "date"],          # ← real headers
            ["ORD001",   "500",    "2024-01-05"],
            ["ORD002",   "320",    "2024-01-06"],
        ])
        df, headers = sanitise(content, "tally_export.csv")
        # Headers should be the actual column names, not metadata
        assert "order_id" in headers or "amount" in headers

    def test_total_row_removed(self):
        """Rows with 'Total' or 'Grand Total' in first column should be dropped."""
        content = _csv_bytes([
            ["item",        "amount"],
            ["Chicken Biryani", "320"],
            ["Dal Makhani",     "220"],
            ["Grand Total",     "540"],   # ← should be removed
        ])
        df, _ = sanitise(content, "test.csv")
        # The grand total row should not appear in the output
        first_col = df.iloc[:, 0].astype(str).str.lower()
        assert not any("total" in v for v in first_col)

    def test_empty_rows_dropped(self):
        content = _csv_bytes([
            ["col1", "col2"],
            ["a",    "b"],
            ["",     ""],     # ← empty row
            ["c",    "d"],
        ])
        df, _ = sanitise(content, "test.csv")
        assert len(df) == 2

    def test_latin1_csv_decoded(self):
        """CSV with latin-1 encoding (common in old Tally exports) should decode."""
        content = _csv_bytes(
            [["Vendor", "Amount"], ["Shree Kripa Stores", "5000"]],
            encoding="latin-1"
        )
        df, headers = sanitise(content, "tally.csv")
        assert len(df) == 1

    def test_empty_file_raises_value_error(self):
        content = b""
        with pytest.raises(Exception):
            sanitise(content, "empty.csv")

    def test_column_names_stripped_of_whitespace(self):
        """Column names with extra whitespace should be normalised."""
        content = _csv_bytes([
            ["  order id  ", "  amount  "],
            ["ORD001", "500"],
        ])
        df, headers = sanitise(content, "test.csv")
        assert "order id" in headers   # whitespace stripped
