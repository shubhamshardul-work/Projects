"""
CLI entry point for data ingestion.

Usage:
    python ingest.py              # Full ingestion (clears DB first)
    python ingest.py --no-clear   # Ingestion without clearing DB
"""
import argparse
import sys

from src.data_loader import load_all_sheets
from src.neo4j_manager import Neo4jManager
from src.ingestion.ingest_graph import run_full_ingestion
from src.utils.logger import log


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Excel data into Neo4j")
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Skip clearing the database before ingestion",
    )
    parser.add_argument(
        "--excel",
        type=str,
        default=None,
        help="Path to Excel file (overrides .env)",
    )
    args = parser.parse_args()

    try:
        # Load data
        sheets = load_all_sheets(args.excel)

        # Connect to Neo4j
        db = Neo4jManager()
        db.connect()

        # Run ingestion
        counts = run_full_ingestion(
            db=db,
            sheets=sheets,
            clear_first=not args.no_clear,
        )

        log.info(f"\n[bold green]🎉 Done![/]")
        log.info(f"   Nodes:         {counts['nodes']}")
        log.info(f"   Relationships: {counts['relationships']}")

        db.close()

    except Exception as e:
        log.error(f"[bold red]Ingestion failed:[/] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
