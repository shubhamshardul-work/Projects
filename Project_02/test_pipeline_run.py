"""
Test runner: execute the full LangGraph pipeline end-to-end against
the sample SOW contract using mapper_mode=llm.

Before running:
  - Clears stale mapped-result caches
  - Purges all existing nodes from Neo4j for a clean slate

Usage:
    python test_pipeline_run.py
"""

import sys
import os
import logging
import json
import shutil
from pathlib import Path

# Ensure we can import from app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Use Groq — Gemini daily free-tier quota exhausted from earlier test runs
os.environ["LLM_PROVIDER"] = "groq"

from app.pipeline.graph_workflow import build_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_pipeline_run")

SAMPLE_FILE = os.path.join(
    os.path.dirname(__file__), "data", "raw", "sample_sow_contract.txt"
)


def cleanup_before_run():
    """Clear stale caches and Neo4j data so we get a fresh test."""
    # 1. Remove old mapped results
    mapped_dir = os.path.join(os.path.dirname(__file__), "data", "mapped")
    if os.path.isdir(mapped_dir):
        for f in Path(mapped_dir).glob("*.json"):
            f.unlink()
            logger.info("Removed stale mapped file: %s", f.name)

    # 2. Clear Neo4j — delete all nodes and relationships
    try:
        from app.graph_db.neo4j_client import Neo4jClient
        client = Neo4jClient()
        client.verify_connectivity()
        client.query("MATCH (n) DETACH DELETE n")
        logger.info("Neo4j cleared — all nodes and relationships deleted")
    except Exception as e:
        logger.warning("Could not clear Neo4j: %s", e)


def run():
    if not Path(SAMPLE_FILE).exists():
        logger.error("Sample file not found: %s", SAMPLE_FILE)
        sys.exit(1)

    # ── Pre-run cleanup ─────────────────────────────────────────────────
    logger.info("=" * 70)
    logger.info("PRE-RUN CLEANUP")
    logger.info("=" * 70)
    cleanup_before_run()

    # ── Build pipeline ──────────────────────────────────────────────────
    logger.info("=" * 70)
    logger.info("BUILDING PIPELINE")
    logger.info("=" * 70)

    graph, checkpointer = build_pipeline()

    thread_id = "test-run-clean-001"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "file_path": SAMPLE_FILE,
        "client_name": "Meridian Global Solutions Inc.",
        "project_name": "Enterprise Data Platform Modernization",
        "mapper_mode": "llm",
    }

    # ── Execute ─────────────────────────────────────────────────────────
    logger.info("=" * 70)
    logger.info("STARTING PIPELINE  (mapper_mode=llm)")
    logger.info("File: %s", SAMPLE_FILE)
    logger.info("=" * 70)

    result = None
    step_count = 0
    try:
        for event in graph.stream(initial_state, config, stream_mode="values"):
            step_count += 1
            status = event.get("status", "?")
            logger.info("[Step %d] status=%s", step_count, status)
            result = event
    except Exception as e:
        logger.exception("Pipeline execution failed")
        print(f"\n{'='*70}")
        print(f"PIPELINE FAILED at step {step_count}")
        print(f"Error: {e}")
        print(f"{'='*70}")
        sys.exit(1)

    # Check if interrupted for human review
    snapshot = graph.get_state(config)
    is_interrupted = bool(
        snapshot.tasks
        and any(hasattr(t, "interrupts") and t.interrupts for t in snapshot.tasks)
    )

    if is_interrupted:
        logger.info("Pipeline paused for HUMAN REVIEW — auto-approving all items")
        review_items = result.get("review_items", [])
        decisions = [
            {"item_id": item["item_id"], "action": "approve"}
            for item in review_items
        ]

        from langgraph.types import Command
        for event in graph.stream(Command(resume=decisions), config, stream_mode="values"):
            step_count += 1
            status = event.get("status", "?")
            logger.info("[Step %d] status=%s (post-review)", step_count, status)
            result = event

    # ── Print summary ───────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("PIPELINE COMPLETED")
    print(f"{'='*70}")
    print(f"Status:       {result.get('status', '?')}")
    print(f"Document ID:  {result.get('document_id', '?')}")

    summary = result.get("ingestion_summary", {})
    if summary:
        print(f"Nodes created: {summary.get('nodes_created', 0)}")
        print(f"Rels created:  {summary.get('relationships_created', 0)}")
        errors = summary.get("errors", [])
        if errors:
            print(f"Errors:        {len(errors)}")
            for e in errors:
                print(f"  - {e}")

    mapped = result.get("mapped_result", {})
    if mapped:
        print(f"\nMapped Result:")
        print(f"  Document type: {mapped.get('document_type', '?')}")
        print(f"  Nodes: {len(mapped.get('nodes', []))}")
        print(f"  Relationships: {len(mapped.get('relationships', []))}")
        print(f"  Unmapped entities: {len(mapped.get('unmapped_entities', []))}")
        warnings = mapped.get("warnings", [])
        print(f"  Warnings: {len(warnings)}")
        for w in warnings:
            # Truncate long warning strings
            print(f"    - {w[:120]}{'...' if len(w) > 120 else ''}")

    review_items = result.get("review_items", [])
    if review_items:
        print(f"\nReview Items ({len(review_items)}):")
        for item in review_items:
            print(f"  - [{item.get('item_id')}] {item.get('entity_name')} — {item.get('reason')}")

    print(f"\n{'='*70}")
    print("Check data/extracted/ and data/mapped/ for cached outputs.")
    print(f"{'='*70}\n")

    # ── Post-run verification ───────────────────────────────────────────
    print("=" * 70)
    print("NEO4J VERIFICATION")
    print("=" * 70)
    try:
        from app.graph_db.neo4j_client import Neo4jClient
        client = Neo4jClient()
        labels = client.query("MATCH (n) RETURN labels(n) AS lbl, count(n) AS cnt ORDER BY cnt DESC")
        rels = client.query("MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt ORDER BY cnt DESC")
        print("Node labels:")
        for row in labels:
            print(f"  {row['lbl']}: {row['cnt']}")
        print(f"Relationship types:")
        for row in rels:
            print(f"  {row['rel']}: {row['cnt']}")
    except Exception as e:
        print(f"Could not query Neo4j: {e}")


if __name__ == "__main__":
    run()
