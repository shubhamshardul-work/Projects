#!/usr/bin/env python3
"""
Build script for the GenAI News Agent website.

Scans 'Gen AI News Agent/reports/' for markdown reports,
generates a reports-index.json, and assembles the final
site into 'site-build/'.
"""

import json
import os
import re
import shutil
from pathlib import Path

REPORTS_DIR = Path("Gen AI News Agent/reports")
SITE_SRC    = Path("site-src")
SITE_BUILD  = Path("site-build")


def extract_title(filepath: Path) -> str:
    """Extract the first H1/H2 heading from a markdown file, or use filename."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# "):
                    return line.lstrip("# ").strip()
        return filepath.stem.replace("_", " ").title()
    except Exception:
        return filepath.stem


def extract_date_from_filename(filename: str) -> str:
    """
    Extract date string from report filename.
    Handles: genai_news_2026-03-03_08-51-26.md -> 2026-03-03_08-51-26
             genai_news_2026-03-01.md          -> 2026-03-01
    """
    match = re.search(r"(\d{4}-\d{2}-\d{2}(?:_\d{2}-\d{2}-\d{2})?)", filename)
    return match.group(1) if match else filename


def build():
    print("🔨 Building site...")

    # Clean previous build
    if SITE_BUILD.exists():
        shutil.rmtree(SITE_BUILD)

    # Copy site source files
    shutil.copytree(SITE_SRC, SITE_BUILD)
    print(f"  ✅ Copied {SITE_SRC}/ → {SITE_BUILD}/")

    # Copy reports
    reports_out = SITE_BUILD / "reports"
    reports_out.mkdir(exist_ok=True)

    if not REPORTS_DIR.exists():
        print("  ⚠️  No reports directory found. Creating empty index.")
        index = []
    else:
        report_files = sorted(REPORTS_DIR.glob("*.md"), reverse=True)
        index = []
        for rp in report_files:
            shutil.copy2(rp, reports_out / rp.name)
            index.append({
                "filename": rp.name,
                "date": extract_date_from_filename(rp.name),
                "title": extract_title(rp),
            })
        print(f"  ✅ Copied {len(report_files)} reports → {reports_out}/")

    # Write reports index
    index_path = SITE_BUILD / "reports-index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    print(f"  ✅ Generated {index_path} ({len(index)} entries)")

    print("🎉 Build complete! Output: site-build/")


if __name__ == "__main__":
    build()
