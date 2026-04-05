"""
Data Loader — reads the Excel workbook and returns clean DataFrames.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from src.config import EXCEL_PATH
from src.utils.logger import log


def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from string columns, drop fully-empty rows."""
    df = df.dropna(how="all")
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str).str.strip()
        # Convert 'None' / 'nan' strings back to actual None
        df[col] = df[col].replace({"None": None, "nan": None, "": None})
    return df


def load_all_sheets(path: str | None = None) -> Dict[str, pd.DataFrame]:
    """
    Load every sheet (except 'Org Summary') from the Excel file.

    Returns:
        dict mapping sheet name → cleaned DataFrame.
    """
    path = path or EXCEL_PATH
    log.info(f"[bold green]Loading Excel[/] from {path}")

    if not Path(path).exists():
        raise FileNotFoundError(f"Excel file not found: {path}")

    xls = pd.ExcelFile(path, engine="openpyxl")
    sheets: Dict[str, pd.DataFrame] = {}

    skip = {"Org Summary"}

    for name in xls.sheet_names:
        if name in skip:
            log.info(f"  ⏭  Skipping sheet: {name}")
            continue
        df = pd.read_excel(xls, sheet_name=name)
        df = _clean_df(df)
        sheets[name] = df
        log.info(f"  ✅ {name}: {len(df)} rows × {len(df.columns)} cols")

    return sheets


def load_sheet(sheet_name: str, path: str | None = None) -> pd.DataFrame:
    """Load a single sheet by name."""
    path = path or EXCEL_PATH
    df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
    return _clean_df(df)
