"""
LangGraph state-machine pipeline for the entire document processing workflow.

Flow:
  START → load_and_preprocess → extract_with_diffbot
        → [map_with_rules | map_with_llm]  (conditional on mapper_mode)
        → validate_and_check
        → [human_review | ingest_to_neo4j]  (conditional on needs_review)
        → ingest_to_neo4j → END
"""

from __future__ import annotations

import logging
from pathlib import Path

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from app.models.schemas import (
    PipelineState,
    DocumentExtractionResult,
    ReviewItem,
    ReviewDecision,
    GraphNode,
)
from app.models.ontology import NodeType
from app.config import CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

# ── Node functions ──────────────────────────────────────────────────────────


def load_and_preprocess(state: PipelineState) -> dict:
    """Load the document, extract text, clean, split into sections."""
    from app.ingest.document_loader import load_document
    from app.ingest.preprocessor import preprocess_document
    from app.ingest.document_registry import register_document

    file_path = state["file_path"]
    logger.info("Loading document: %s", file_path)

    record = register_document(
        file_path,
        client_name=state.get("client_name", ""),
        project_name=state.get("project_name", ""),
    )

    raw = load_document(file_path)
    processed = preprocess_document(raw)

    logger.info("[%s] %d sections detected", record.document_id, len(processed["sections"]))

    run_folder = state.get("run_folder")
    if run_folder:
        import os, json
        with open(os.path.join(run_folder, "1_raw_document.txt"), "w", encoding="utf-8") as f:
            f.write(processed["full_text"])
        with open(os.path.join(run_folder, "1_sections.json"), "w", encoding="utf-8") as f:
            json.dump(processed["sections"], f, indent=2)

    return {
        "document_id": record.document_id,
        "raw_text": processed["full_text"],
        "cleaned_text": processed["cleaned_text"],
        "sections": processed["sections"],
        "status": "preprocessed",
    }


def extract_with_diffbot(state: PipelineState) -> dict:
    """Send each section to Diffbot NLP API and cache results."""
    from app.extraction.diffbot_client import extract_by_section
    from app.ingest.document_registry import update_status

    doc_id = state["document_id"]
    sections = state["sections"]

    logger.info("[%s] Extracting via Diffbot (%d sections)…", doc_id, len(sections))
    update_status(doc_id, "extracting")

    diffbot_results = extract_by_section(sections, doc_id)

    total_entities = sum(len(r.get("entities", [])) for r in diffbot_results)
    total_rels = sum(len(r.get("relationships", [])) for r in diffbot_results)
    total_props = sum(len(r.get("properties", [])) for r in diffbot_results)
    logger.info(
        "[%s] Diffbot: %d entities, %d relationships, %d properties",
        doc_id, total_entities, total_rels, total_props,
    )

    update_status(doc_id, "extracted")
    
    run_folder = state.get("run_folder")
    if run_folder:
        import os, json
        with open(os.path.join(run_folder, "2_diffbot_extracted.json"), "w", encoding="utf-8") as f:
            json.dump(diffbot_results, f, indent=2)

    return {"diffbot_results": diffbot_results, "status": "extracted"}


def map_with_rules(state: PipelineState) -> dict:
    """Rule-based mapping (no LLM)."""
    from app.mapper.rule_mapper import map_document_rule_based, save_mapped_result
    from app.ingest.document_registry import update_status

    doc_id = state["document_id"]
    logger.info("[%s] Mapping with RULES", doc_id)
    update_status(doc_id, "mapping")

    result = map_document_rule_based(
        diffbot_results=state["diffbot_results"],
        document_id=doc_id,
        file_name=Path(state["file_path"]).name,
        source_file=state["file_path"],
        text=state["cleaned_text"],
    )

    save_mapped_result(result)
    update_status(doc_id, "mapped", document_type=result.document_type)
    logger.info("[%s] Mapped: %d nodes, %d rels", doc_id, len(result.nodes), len(result.relationships))

    run_folder = state.get("run_folder")
    if run_folder:
        import os, json
        with open(os.path.join(run_folder, "3_mapped_results.json"), "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

    return {"mapped_result": result.model_dump(), "status": "mapped"}


def map_with_llm(state: PipelineState) -> dict:
    """LLM-based mapping."""
    from app.mapper.llm_mapper import map_document_llm_based, save_mapped_result
    from app.ingest.document_registry import update_status

    doc_id = state["document_id"]
    logger.info("[%s] Mapping with LLM", doc_id)
    update_status(doc_id, "mapping")

    result = map_document_llm_based(
        diffbot_results=state["diffbot_results"],
        document_id=doc_id,
        file_name=Path(state["file_path"]).name,
        source_file=state["file_path"],
        text=state["cleaned_text"],
    )

    save_mapped_result(result)
    update_status(doc_id, "mapped", document_type=result.document_type)
    logger.info("[%s] Mapped: %d nodes, %d rels", doc_id, len(result.nodes), len(result.relationships))

    run_folder = state.get("run_folder")
    if run_folder:
        import os, json
        with open(os.path.join(run_folder, "3_mapped_results.json"), "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

    return {"mapped_result": result.model_dump(), "status": "mapped"}


def validate_and_check(state: PipelineState) -> dict:
    """
    Validate the mapped result and flag items for human review.
    Items flagged: unmapped entities, low-confidence nodes, missing required fields.
    """
    mapped = DocumentExtractionResult(**state["mapped_result"])
    review_items: list[dict] = []

    # Flag unmapped entities
    for i, ue in enumerate(mapped.unmapped_entities):
        review_items.append(
            ReviewItem(
                item_id=f"unmapped-{i}",
                item_type="node",
                entity_name=ue.get("name", "unknown"),
                diffbot_type=ue.get("type"),
                section_heading=ue.get("section", ""),
                reason="No ontology match found",
                confidence=0.0,
            ).model_dump()
        )

    # Flag low-confidence nodes (relevant for LLM mapper)
    for node_dict in mapped.model_dump()["nodes"]:
        confidence = node_dict.get("confidence", 1.0)
        if confidence < CONFIDENCE_THRESHOLD:
            review_items.append(
                ReviewItem(
                    item_id=f"low-conf-{node_dict['id']}",
                    item_type="node",
                    entity_name=node_dict.get("properties", {}).get("name", node_dict["id"]),
                    suggested_node_type=node_dict["type"],
                    confidence=confidence,
                    reason=f"Low confidence ({confidence:.2f})",
                ).model_dump()
            )

    needs_review = len(review_items) > 0
    new_status = "review" if needs_review else "validated"
    logger.info(
        "[%s] Validation: %d items flagged for review",
        state["document_id"],
        len(review_items),
    )

    return {
        "needs_review": needs_review,
        "review_items": review_items,
        "status": new_status,
    }


def human_review(state: PipelineState) -> dict:
    """
    Pause for human review using LangGraph interrupt.
    When resumed, apply human decisions to the mapped result.
    """
    review_items = state.get("review_items", [])

    # Interrupt and wait for human decisions
    human_decisions = interrupt(
        {
            "message": "Items require human review. Please approve, edit, or reject each item.",
            "review_items": review_items,
        }
    )

    # Apply decisions to mapped_result
    mapped = DocumentExtractionResult(**state["mapped_result"])
    decisions = human_decisions if isinstance(human_decisions, list) else []

    for decision_data in decisions:
        decision = ReviewDecision(**decision_data) if isinstance(decision_data, dict) else decision_data

        if decision.action == "reject":
            # Remove from unmapped (just acknowledge rejection)
            continue

        if decision.action == "edit" and decision.new_node_type:
            # Add edited entity as a new node
            try:
                node_type = NodeType(decision.new_node_type)
                new_node = GraphNode(
                    type=node_type,
                    id=f"{mapped.document_id}_reviewed_{decision.item_id}",
                    properties=decision.new_properties or {"name": decision.item_id},
                    confidence=1.0,
                )
                mapped.nodes.append(new_node)
            except (ValueError, KeyError):
                pass

        # "approve" — keep as-is, no changes needed

    logger.info("[%s] Human review applied %d decisions", state["document_id"], len(decisions))

    return {
        "mapped_result": mapped.model_dump(),
        "human_decisions": decisions,
        "status": "reviewed",
    }


def ingest_to_neo4j(state: PipelineState) -> dict:
    """Load the final mapped result into Neo4j."""
    from app.graph_db.neo4j_client import Neo4jClient
    from app.graph_db.loader import load_extraction_result
    from app.graph_db.queries import create_indexes
    from app.ingest.document_registry import update_status

    doc_id = state["document_id"]
    mapped = DocumentExtractionResult(**state["mapped_result"])

    logger.info("[%s] Ingesting into Neo4j…", doc_id)
    update_status(doc_id, "ingesting")

    try:
        client = Neo4jClient()
        client.verify_connectivity()
        create_indexes(client)

        summary = load_extraction_result(client, mapped)

        update_status(doc_id, "ingested")
        logger.info(
            "[%s] Neo4j: %d nodes, %d rels",
            doc_id, summary["nodes_created"], summary["relationships_created"],
        )

        run_folder = state.get("run_folder")
        if run_folder:
            import os, json
            with open(os.path.join(run_folder, "4_neo4j_ingestion_summary.json"), "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)

        return {"ingestion_summary": summary, "status": "completed"}

    except Exception as e:
        logger.exception("[%s] Neo4j ingestion failed", doc_id)
        update_status(doc_id, "failed")
        
        err_summary = {"errors": [str(e)]}
        run_folder = state.get("run_folder")
        if run_folder:
            import os, json
            with open(os.path.join(run_folder, "4_neo4j_ingestion_summary.json"), "w", encoding="utf-8") as f:
                json.dump(err_summary, f, indent=2)
                
        return {"ingestion_summary": err_summary, "status": "failed", "error": str(e)}


# ── Routing functions ───────────────────────────────────────────────────────


def route_mapper(state: PipelineState) -> str:
    """Route to rule or LLM mapper based on mapper_mode."""
    return state.get("mapper_mode", "rule")


def route_review(state: PipelineState) -> str:
    """Route to human review or straight to ingestion."""
    if state.get("needs_review", False):
        return "human_review"
    return "ingest"


# ── Build the graph ─────────────────────────────────────────────────────────


def build_pipeline() -> tuple:
    """
    Build and compile the LangGraph pipeline.
    Returns (compiled_graph, checkpointer).
    """
    builder = StateGraph(PipelineState)

    # Nodes
    builder.add_node("load_and_preprocess", load_and_preprocess)
    builder.add_node("extract_with_diffbot", extract_with_diffbot)
    builder.add_node("map_with_rules", map_with_rules)
    builder.add_node("map_with_llm", map_with_llm)
    builder.add_node("validate_and_check", validate_and_check)
    builder.add_node("human_review", human_review)
    builder.add_node("ingest_to_neo4j", ingest_to_neo4j)

    # Edges
    builder.add_edge(START, "load_and_preprocess")
    builder.add_edge("load_and_preprocess", "extract_with_diffbot")

    # Conditional: mapper mode
    builder.add_conditional_edges(
        "extract_with_diffbot",
        route_mapper,
        {"rule": "map_with_rules", "llm": "map_with_llm"},
    )

    builder.add_edge("map_with_rules", "validate_and_check")
    builder.add_edge("map_with_llm", "validate_and_check")

    # Conditional: human review or ingest
    builder.add_conditional_edges(
        "validate_and_check",
        route_review,
        {"human_review": "human_review", "ingest": "ingest_to_neo4j"},
    )

    builder.add_edge("human_review", "ingest_to_neo4j")
    builder.add_edge("ingest_to_neo4j", END)

    # Compile with memory checkpointer for HITL
    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    return graph, checkpointer
