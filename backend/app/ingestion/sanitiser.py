"""
sanitiser.py — Pre-processing for real-world Indian SMB Excel and CSV files.

Handles:
- Header row not in row 0 (common in Tally exports)
- Merged cell artifacts
- Subtotal/total rows mixed with data
- Multi-sheet Excel files
- Encoding issues in CSV files
- Magic byte validation for security
"""
from __future__ import annotations
import io
import re
import zipfile
import logging
import pandas as pd
import numpy as np
from typing import Tuple, List

logger = logging.getLogger(__name__)

# ── Security: File content validation ─────────────────────────────────────────

MAGIC_BYTES = {
    "csv":  None,                         # no magic bytes — validate encoding
    "xlsx": b"PK\x03\x04",               # ZIP format (OOXML)
    "xls":  b"\xd0\xcf\x11\xe0",         # Compound Document
}


def validate_file(content: bytes, filename: str) -> Tuple[bool, str]:
    """
    Validate file content before storing or parsing.
    Returns (is_valid, error_message).
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ("csv", "xlsx", "xls"):
        return False, f"Unsupported file type: .{ext}"

    if ext == "xlsx":
        # Must be a valid ZIP file (OOXML is ZIP-based)
        if not content[:4] == MAGIC_BYTES["xlsx"]:
            return False, "File is not a valid Excel (.xlsx) file."
        if not zipfile.is_zipfile(io.BytesIO(content)):
            return False, "File is not a valid Excel (.xlsx) file."

    elif ext == "xls":
        if not content[:4] == MAGIC_BYTES["xls"]:
            return False, "File is not a valid Excel (.xls) file."

    elif ext == "csv":
        # Try to decode as text — reject binary content
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                content.decode(enc)
                return True, ""
            except UnicodeDecodeError:
                continue
        return False, "CSV file has unrecognisable encoding. Please save as UTF-8."

    return True, ""


# ── CSV loading ───────────────────────────────────────────────────────────────

def _load_csv(content: bytes) -> pd.DataFrame:
    """Try multiple encodings. Return first successful parse."""
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(
                io.BytesIO(content),
                encoding=enc,
                skip_blank_lines=True,
                on_bad_lines="skip",
                low_memory=False,
            )
            if not df.empty:
                return df
        except Exception:
            continue
    raise ValueError("Could not parse CSV with any supported encoding.")


# ── Excel loading ─────────────────────────────────────────────────────────────

def _load_excel(content: bytes, ext: str) -> pd.DataFrame:
    """Load Excel, selecting the most data-rich sheet."""
    buf = io.BytesIO(content)
    engine = "openpyxl" if ext == "xlsx" else "xlrd"

    try:
        xl = pd.ExcelFile(buf, engine=engine)
    except Exception as e:
        raise ValueError(f"Could not open Excel file: {e}")

    best_df = None
    best_rows = 0

    for sheet in xl.sheet_names:
        try:
            df = xl.parse(sheet)
            if len(df) > best_rows:
                best_rows = len(df)
                best_df = df
        except Exception:
            continue

    if best_df is None or best_df.empty:
        raise ValueError("Excel file contains no readable data.")

    return best_df


# ── Header detection ──────────────────────────────────────────────────────────

def _find_header_row(df: pd.DataFrame) -> int:
    """
    Detect actual header row index. Tally and some POS exports
    embed metadata rows above the actual column headers.

    Heuristic: the header row has the most non-null string cells
    and no large numeric values.
    """
    best_row = 0
    best_score = 0

    for i in range(min(10, len(df))):
        row = df.iloc[i]
        # Count non-null string-like cells
        str_count = sum(1 for v in row if isinstance(v, str) and len(str(v).strip()) > 1)
        # Penalise rows with large numbers (likely data rows, not headers)
        num_count = sum(1 for v in row
                       if isinstance(v, (int, float)) and not np.isnan(float(v)) and abs(float(v)) > 1000)
        score = str_count - (num_count * 0.5)
        if score > best_score:
            best_score = score
            best_row = i

    return best_row


def _apply_header_row(df: pd.DataFrame, header_row: int) -> pd.DataFrame:
    """Reconstruct DataFrame with detected header row as column names."""
    if header_row == 0:
        return df
    new_columns = df.iloc[header_row].astype(str).tolist()
    df = df.iloc[header_row + 1:].copy()
    df.columns = new_columns
    df = df.reset_index(drop=True)
    return df


# ── Data cleaning ─────────────────────────────────────────────────────────────

def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names: strip whitespace, collapse spaces."""
    df.columns = [
        re.sub(r"\s+", " ", str(c).strip())
        for c in df.columns
    ]
    # Drop columns with empty or unnamed headers
    #df = df.loc[:, ~df.columns.str.match(r"^(Unnamed|nan|\s*)")]
    # FIXED — only drop truly unnamed columns pandas auto-generates
    df = df.loc[:, ~df.columns.str.match(r'^(Unnamed: \d+|nan)$')]
    return df


def _drop_total_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove subtotal/total rows mixed into data.
    Heuristic: rows where the first meaningful column contains
    keywords like 'total', 'subtotal', 'grand total', 'sum'.
    """
    if df.empty:
        return df

    first_col = df.iloc[:, 0].astype(str).str.lower().str.strip()
    total_mask = first_col.str.contains(
        r"\b(total|subtotal|grand total|sum|avg|average|net)\b",
        regex=True, na=False
    )
    removed = total_mask.sum()
    if removed > 0:
        logger.debug(f"Removed {removed} total/subtotal rows")
    return df[~total_mask].copy()


def _drop_empty_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows that are entirely empty or whitespace."""
    return df.dropna(how="all").reset_index(drop=True)


def _strip_merged_artifacts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Excel merged cells produce NaN in all but the first cell.
    Forward-fill string columns that look like they result from merges.
    Only applies to columns that look like category/label columns (not numeric).
    """
    for col in df.columns:
        if df[col].dtype == object:
            null_frac = df[col].isna().mean()
            # If > 30% nulls in a string column, likely merged cells
            if null_frac > 0.30:
                df[col] = df[col].fillna(method="ffill")
    return df


# ── Main entry point ──────────────────────────────────────────────────────────

def sanitise(content: bytes, filename: str) -> Tuple[pd.DataFrame, List[str]]:
    """
    Full sanitisation pipeline. Returns (cleaned_df, headers).

    Steps:
    1. Validate file (magic bytes, encoding)
    2. Load raw DataFrame
    3. Detect and apply header row
    4. Clean column names
    5. Drop total/empty rows
    6. Strip merged cell artifacts
    """
    is_valid, error = validate_file(content, filename)
    if not is_valid:
        raise ValueError(f"Invalid file: {error}")

    ext = filename.rsplit(".", 1)[-1].lower()

    # Load
    if ext == "csv":
        df = _load_csv(content)
    else:
        df = _load_excel(content, ext)

    if df.empty:
        raise ValueError("File is empty or contains no data rows.")

    # Find and apply real header row
    header_row = _find_header_row(df)
    if header_row > 0:
        logger.debug(f"Header detected at row {header_row} (not row 0)")
        df = _apply_header_row(df, header_row)

    # Clean
    df = _clean_columns(df)
    df = _strip_merged_artifacts(df)
    df = _drop_total_rows(df)
    df = _drop_empty_rows(df)

    if df.empty:
        raise ValueError("File has no data rows after cleaning.")

    headers = list(df.columns)
    logger.info(f"Sanitised {filename}: {len(df)} rows, {len(headers)} columns")
    return df, headers
