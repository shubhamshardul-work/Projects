"""
Data Loader — reads any Excel or CSV file(s) and returns clean DataFrames.

Supports:
  - Single Excel file (.xlsx, .xls) → loads all sheets
  - Single CSV file (.csv) → loads as one table
  - Directory of CSV files → loads each as a table
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

from src.utils.logger import log


def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from string columns, drop fully-empty rows."""
    df = df.dropna(how="all").copy()
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"None": None, "nan": None, "": None})
    return df


def _is_data_sheet(df: pd.DataFrame) -> bool:
    """
    Heuristic: skip sheets that look like dashboards/summaries.
    A valid data sheet has a clear header row with at least 2 columns
    and more than 1 data row.
    """
    if len(df) < 2 or len(df.columns) < 2:
        return False
    # Check if first row of column names looks like headers (not merged cells)
    null_headers = sum(1 for c in df.columns if "Unnamed" in str(c))
    if null_headers > len(df.columns) * 0.5:
        return False
    return True


def load_file(path: str) -> Dict[str, pd.DataFrame]:
    """
    Load data from a file or directory.

    Args:
        path: Path to an Excel file, CSV file, or directory of CSVs.

    Returns:
        Dict mapping table name → cleaned DataFrame.
    """
    p = Path(path)
    log.info(f"[bold green]Loading data[/] from {p}")

    if not p.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    tables: Dict[str, pd.DataFrame] = {}

    if p.is_dir():
        # Directory of CSV files
        csv_files = sorted(p.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {path}")
        for csv_path in csv_files:
            name = csv_path.stem
            df = pd.read_csv(csv_path)
            df = _clean_df(df)
            if _is_data_sheet(df):
                tables[name] = df
                log.info(f"  ✅ {name}: {len(df)} rows × {len(df.columns)} cols")
            else:
                log.info(f"  ⏭  Skipping {name} (doesn't look like data)")

    elif p.suffix.lower() in (".xlsx", ".xls"):
        # Excel file — load all sheets
        xls = pd.ExcelFile(path, engine="openpyxl")
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            df = _clean_df(df)
            if _is_data_sheet(df):
                tables[sheet_name] = df
                log.info(f"  ✅ {sheet_name}: {len(df)} rows × {len(df.columns)} cols")
            else:
                log.info(f"  ⏭  Skipping sheet: {sheet_name} (doesn't look like data)")

    elif p.suffix.lower() == ".csv":
        # Single CSV file
        name = p.stem
        df = pd.read_csv(path)
        df = _clean_df(df)
        tables[name] = df
        log.info(f"  ✅ {name}: {len(df)} rows × {len(df.columns)} cols")

    else:
        raise ValueError(f"Unsupported file type: {p.suffix}")

    log.info(f"[bold green]Loaded {len(tables)} tables[/]")
    return tables
