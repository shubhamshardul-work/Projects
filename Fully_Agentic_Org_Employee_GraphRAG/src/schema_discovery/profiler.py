"""
Data Profiler — extracts metadata from any CSV/Excel for LLM consumption.

Produces a structured summary of every table: column names, dtypes,
cardinality, null ratios, sample values, and detected foreign key candidates.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.utils.logger import log


# ───────────────────────────────────────────────────────────────────────
# Column-level profiling
# ───────────────────────────────────────────────────────────────────────

def _infer_dtype(series: pd.Series) -> str:
    """Map pandas dtype to a simplified type string."""
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    return "string"


def _profile_column(series: pd.Series) -> Dict[str, Any]:
    """Build a metadata dict for a single column."""
    non_null = series.dropna()
    unique_count = non_null.nunique()
    total = len(series)
    null_count = int(series.isna().sum())

    # Sample up to 5 unique values
    samples = non_null.unique()[:5].tolist()
    # Convert any non-JSON-serializable types
    safe_samples = []
    for s in samples:
        if isinstance(s, pd.Timestamp):
            safe_samples.append(s.isoformat())
        else:
            safe_samples.append(str(s))

    return {
        "name": series.name,
        "dtype": _infer_dtype(series),
        "total_count": total,
        "unique_count": unique_count,
        "null_count": null_count,
        "null_pct": round(null_count / total * 100, 1) if total > 0 else 0,
        "sample_values": safe_samples,
    }


# ───────────────────────────────────────────────────────────────────────
# Table-level profiling
# ───────────────────────────────────────────────────────────────────────

def _profile_table(name: str, df: pd.DataFrame) -> Dict[str, Any]:
    """Build a metadata dict for a single table/sheet."""
    columns = [_profile_column(df[col]) for col in df.columns]

    # Build a sample of first 3 rows as dicts
    sample_rows = []
    for _, row in df.head(3).iterrows():
        row_dict = {}
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                row_dict[col] = None
            elif isinstance(val, pd.Timestamp):
                row_dict[col] = val.isoformat()
            else:
                row_dict[col] = str(val)
        sample_rows.append(row_dict)

    return {
        "name": name,
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": columns,
        "sample_rows": sample_rows,
    }


# ───────────────────────────────────────────────────────────────────────
# Foreign key detection
# ───────────────────────────────────────────────────────────────────────

def _detect_foreign_keys(
    tables: Dict[str, pd.DataFrame],
) -> List[Dict[str, str]]:
    """
    Heuristic FK detection: if column X in table A has values that are
    a subset of column Y in table B (where Y looks like a primary key),
    then X → Y is a likely foreign key.
    """
    # First, identify likely primary keys (first column with all unique values)
    pk_map: Dict[str, Dict[str, set]] = {}  # table_name -> {col_name: set(values)}
    for tname, df in tables.items():
        for col in df.columns:
            series = df[col].dropna()
            if len(series) > 0 and series.nunique() == len(series):
                if tname not in pk_map:
                    pk_map[tname] = {}
                pk_map[tname][col] = set(series.astype(str))

    # Now check every column in every table for FK matches
    fk_candidates = []
    for tname, df in tables.items():
        for col in df.columns:
            series = df[col].dropna()
            if len(series) == 0:
                continue
            col_values = set(series.astype(str))

            # Skip if this column is itself a PK in its own table
            if tname in pk_map and col in pk_map[tname]:
                continue

            # Check against all PKs in other tables
            for ref_table, pks in pk_map.items():
                if ref_table == tname:
                    continue
                for ref_col, ref_values in pks.items():
                    # FK if col values are a subset of ref values (with tolerance)
                    overlap = col_values & ref_values
                    if len(overlap) > 0 and len(overlap) / len(col_values) >= 0.8:
                        fk_candidates.append({
                            "source_table": tname,
                            "source_column": col,
                            "target_table": ref_table,
                            "target_column": ref_col,
                            "match_pct": round(len(overlap) / len(col_values) * 100, 1),
                        })

    return fk_candidates


# ───────────────────────────────────────────────────────────────────────
# Public API
# ───────────────────────────────────────────────────────────────────────

def profile_data(
    tables: Dict[str, pd.DataFrame],
) -> Dict[str, Any]:
    """
    Profile all tables and detect foreign keys.

    Args:
        tables: dict of table_name → DataFrame

    Returns:
        Complete profiling result with table metadata + FK candidates.
    """
    log.info(f"[bold cyan]Profiler[/] Profiling {len(tables)} tables …")

    table_profiles = []
    for name, df in tables.items():
        profile = _profile_table(name, df)
        table_profiles.append(profile)
        log.info(
            f"  ✅ {name}: {profile['row_count']} rows × "
            f"{profile['column_count']} cols"
        )

    fk_candidates = _detect_foreign_keys(tables)
    log.info(f"  🔗 Detected {len(fk_candidates)} foreign key candidates")

    return {
        "tables": table_profiles,
        "foreign_key_candidates": fk_candidates,
    }


def profile_to_text(profile: Dict[str, Any]) -> str:
    """Format the profile as a compact text string for LLM consumption."""
    lines = []
    lines.append("=== DATA PROFILE ===\n")

    for t in profile["tables"]:
        lines.append(f"TABLE: {t['name']} ({t['row_count']} rows × {t['column_count']} columns)")
        lines.append("  Columns:")
        for c in t["columns"]:
            lines.append(
                f"    - {c['name']} ({c['dtype']}) | "
                f"unique={c['unique_count']}, nulls={c['null_count']} ({c['null_pct']}%) | "
                f"samples: {c['sample_values'][:3]}"
            )
        if t["sample_rows"]:
            lines.append(f"  Sample Row: {json.dumps(t['sample_rows'][0], default=str)}")
        lines.append("")

    if profile["foreign_key_candidates"]:
        lines.append("DETECTED FOREIGN KEY CANDIDATES:")
        for fk in profile["foreign_key_candidates"]:
            lines.append(
                f"  {fk['source_table']}.{fk['source_column']} → "
                f"{fk['target_table']}.{fk['target_column']} "
                f"({fk['match_pct']}% match)"
            )
        lines.append("")

    return "\n".join(lines)
