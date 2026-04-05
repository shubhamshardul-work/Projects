"""
CLI entry point for data ingestion.

Fully agentic pipeline:
  1. Load data from any CSV/Excel
  2. Profile the data (extract metadata)
  3. Use LLM to infer graph schema
  4. Dynamically ingest into Neo4j

Usage:
    python ingest.py <path_to_file_or_dir>
    python ingest.py "Source Input/accenIndia_org_model.xlsx"
    python ingest.py data/csvs/
    python ingest.py --mapping mappings/my_schema.json  # reuse saved mapping
"""
import argparse
import sys
from pathlib import Path

from src.data_loader import load_file
from src.schema_discovery.profiler import profile_data
from src.schema_discovery.schema_agent import infer_graph_schema, load_mapping
from src.neo4j_manager import Neo4jManager
from src.ingestion.dynamic_ingest import run_dynamic_ingestion
from src.config import MAPPING_DIR
from src.utils.logger import log


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agentic Graph Ingestion: any CSV/Excel → Neo4j"
    )
    parser.add_argument(
        "source",
        type=str,
        help="Path to Excel file, CSV file, or directory of CSVs",
    )
    parser.add_argument(
        "--mapping",
        type=str,
        default=None,
        help="Path to a saved GraphMappingModel JSON (skip schema inference)",
    )
    parser.add_argument(
        "--save-mapping",
        type=str,
        default=None,
        help="Save the inferred mapping to this path",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Skip clearing the database before ingestion",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Override LLM provider (groq, gemini, openai)",
    )
    args = parser.parse_args()

    try:
        # 1. Load data
        tables = load_file(args.source)

        if not tables:
            log.error("[bold red]No data tables found in the source.[/]")
            sys.exit(1)

        # 2. Get or infer mapping
        if args.mapping:
            log.info(f"[bold green]Loading saved mapping[/] from {args.mapping}")
            mapping = load_mapping(args.mapping)
        else:
            # Profile the data
            profile = profile_data(tables)

            # Infer graph schema using LLM
            save_path = args.save_mapping
            if not save_path:
                # Auto-save to mappings dir
                source_name = Path(args.source).stem
                save_path = str(Path(MAPPING_DIR) / f"{source_name}_mapping.json")

            mapping = infer_graph_schema(
                profile=profile,
                llm_provider=args.provider,
                save_path=save_path,
            )

        # 3. Connect to Neo4j
        db = Neo4jManager()
        db.connect()

        # 4. Run dynamic ingestion
        counts = run_dynamic_ingestion(
            db=db,
            tables=tables,
            mapping=mapping,
            clear_first=not args.no_clear,
        )

        log.info(f"\n[bold green]🎉 Done![/]")
        log.info(f"   Nodes:         {counts['nodes']}")
        log.info(f"   Relationships: {counts['relationships']}")

        db.close()

    except Exception as e:
        log.error(f"[bold red]Ingestion failed:[/] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
