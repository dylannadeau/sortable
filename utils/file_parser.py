"""File ingestion and validation — CSV, Excel, and plain text parsing."""

from __future__ import annotations

import io
from typing import Optional

import pandas as pd


def _detect_best_text_column(df: pd.DataFrame) -> Optional[str]:
    """Return the name of the column with the highest proportion of non-null string values."""
    best_col: Optional[str] = None
    best_ratio: float = 0.0
    for col in df.columns:
        str_count = df[col].apply(lambda v: isinstance(v, str) and len(v.strip()) > 0).sum()
        ratio = str_count / len(df) if len(df) > 0 else 0.0
        if ratio > best_ratio:
            best_ratio = ratio
            best_col = col
    if best_ratio < 0.5:
        return None
    return best_col


def _all_columns_numeric(df: pd.DataFrame) -> bool:
    """Return True if every column in the DataFrame is numeric."""
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            non_null = df[col].dropna()
            if len(non_null) == 0:
                continue
            numeric_count = pd.to_numeric(non_null, errors="coerce").notna().sum()
            if numeric_count < len(non_null):
                return False
    return True


def _read_csv(file: io.BufferedIOBase) -> pd.DataFrame:
    """Read a CSV file into a DataFrame."""
    file.seek(0)
    return pd.read_csv(file)


def _read_excel(file: io.BufferedIOBase) -> pd.DataFrame:
    """Read an Excel file into a DataFrame using openpyxl."""
    file.seek(0)
    return pd.read_excel(file, engine="openpyxl")


def _read_text(file: io.BufferedIOBase) -> pd.DataFrame:
    """Read a plain text file (one item per line) into a single-column DataFrame."""
    file.seek(0)
    raw = file.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return pd.DataFrame({"item": lines})


def _get_extension(filename: str) -> str:
    """Extract the lowercase file extension including the dot."""
    dot_idx = filename.rfind(".")
    if dot_idx == -1:
        return ""
    return filename[dot_idx:].lower()


def parse_upload(file) -> tuple[Optional[pd.DataFrame], list[str]]:
    """Parse an uploaded file into a DataFrame and a list of warning/error strings."""
    warnings: list[str] = []

    # --- Determine file extension ---
    filename: str = getattr(file, "name", "")
    ext = _get_extension(filename)

    if ext not in (".csv", ".xlsx", ".xls", ".txt"):
        warnings.append(
            f"Unsupported file type '{ext or '(none)'}'. Please upload a .csv, .xlsx, .xls, or .txt file."
        )
        return None, warnings

    # --- Attempt to read the file ---
    try:
        if ext == ".csv":
            df = _read_csv(file)
        elif ext in (".xlsx", ".xls"):
            df = _read_excel(file)
        else:
            df = _read_text(file)
    except Exception as exc:
        warnings.append(f"Could not read the file — it may be corrupted or in an unexpected format. ({exc})")
        return None, warnings

    # --- Hard block: empty file ---
    if df.empty or (len(df) == 0 and len(df.columns) == 0):
        warnings.append("The file is empty. Please upload a file with at least 2 rows of data.")
        return None, warnings

    # --- Hard block: fewer than 2 data rows ---
    if len(df) < 2:
        warnings.append(
            f"The file only has {len(df)} row of data. At least 2 rows are required."
        )
        return None, warnings

    # --- Hard block: exceeds 50,000 rows ---
    if len(df) > 50_000:
        warnings.append(
            f"The file has {len(df):,} rows, which exceeds the 50,000 row limit. "
            "Please reduce the file size and try again."
        )
        return None, warnings

    # --- Hard block: all columns numeric ---
    if ext != ".txt" and _all_columns_numeric(df):
        warnings.append(
            "All columns in this file appear to be numeric. "
            "At least one column must contain text data."
        )
        return None, warnings

    # --- Hard block: no usable text column (CSV/Excel only) ---
    if ext != ".txt" and _detect_best_text_column(df) is None:
        warnings.append(
            "No column has more than 50% non-empty text values. "
            "Please check that your file contains a column of text items."
        )
        return None, warnings

    # --- Soft warning: large file ---
    if len(df) > 10_000:
        warnings.append(
            f"This file has {len(df):,} rows. Processing may take a while."
        )

    # --- Soft warning: duplicates ---
    text_col = df.columns[0] if ext == ".txt" else _detect_best_text_column(df)
    if text_col is not None and text_col in df.columns:
        dup_count = df[text_col].duplicated().sum()
        if dup_count > 0:
            warnings.append(
                f"{dup_count:,} duplicate item{'s' if dup_count != 1 else ''} detected."
            )

    # --- Soft warning: very short items ---
    if text_col is not None and text_col in df.columns:
        short_count = df[text_col].apply(
            lambda v: isinstance(v, str) and 0 < len(v.strip()) < 2
        ).sum()
        if short_count > 0:
            warnings.append(
                f"{short_count:,} item{'s' if short_count != 1 else ''} "
                f"with fewer than 2 characters detected."
            )

    return df, warnings
