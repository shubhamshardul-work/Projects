#!/usr/bin/env python3
"""
Build script for the unified Portfolio and GenAI News Agent website.

Assembles the final site into 'dist/':
1. Copies 'portfolio-src/' to 'dist/' (root portfolio)
2. Copies 'site-src/' to 'dist/GenAIReport/'
3. Scans 'Gen AI News Agent/reports/' for markdown reports,
   generates a reports-index.json, and copies reports to 'dist/GenAIReport/reports/'
"""

import json
import os
import re
import shutil
from pathlib import Path

REPORTS_DIR = Path("Gen AI News Agent/reports")
GENAI_SRC   = Path("site-src")
PORTFOLIO_SRC = Path("portfolio-src")
DIST_DIR    = Path("dist")


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
    print("🔨 Building unified site...")

    # Clean previous build
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    
    # 1. Copy Portfolio to root of dist
    shutil.copytree(PORTFOLIO_SRC, DIST_DIR)
    print(f"  ✅ Copied {PORTFOLIO_SRC}/ → {DIST_DIR}/")

    # 2. Copy GenAI Report site source to dist/GenAIReport
    genai_out = DIST_DIR / "GenAIReport"
    shutil.copytree(GENAI_SRC, genai_out)
    print(f"  ✅ Copied {GENAI_SRC}/ → {genai_out}/")

    # 3. Process GenAI Reports
    reports_out = genai_out / "reports"
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

    # Write reports index for GenAIReport
    index_path = genai_out / "reports-index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    print(f"  ✅ Generated {index_path} ({len(index)} entries)")

    print("🎉 Unified Build complete! Output: dist/")


if __name__ == "__main__":
    build()
