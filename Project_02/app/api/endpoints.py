"""
FastAPI endpoints for the Contract Intelligence Knowledge Graph.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from langgraph.types import Command

from app.config import RAW_DIR
from app.pipeline.graph_workflow import build_pipeline
from app.rag.graph_rag import create_graph_rag_chain, ask as rag_ask

router = APIRouter()

# ---------------------------------------------------------------------------
# Singletons (lazy-initialised)
# ---------------------------------------------------------------------------

_pipeline = None
_checkpointer = None
_rag_chain = None


def _get_pipeline():
    global _pipeline, _checkpointer
    if _pipeline is None:
        _pipeline, _checkpointer = build_pipeline()
    return _pipeline, _checkpointer


def _get_rag_chain():
    global _rag_chain
    if _rag_chain is None:
        _rag_chain = create_graph_rag_chain()
    return _rag_chain


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ReviewSubmission(BaseModel):
    decisions: list[dict[str, Any]]


class QueryRequest(BaseModel):
    question: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    client_name: str = Query(""),
    project_name: str = Query(""),
    mapper_mode: str = Query("rule", regex="^(rule|llm)$"),
):
    """Upload a document and start the LangGraph pipeline."""
    upload_dir = Path(RAW_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    graph, _ = _get_pipeline()
    thread_id = uuid.uuid4().hex[:12]
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "file_path": str(dest),
        "client_name": client_name,
        "project_name": project_name,
        "mapper_mode": mapper_mode,
    }

    # Run the pipeline (may pause at human_review interrupt)
    result = None
    for event in graph.stream(initial_state, config, stream_mode="values"):
        result = event

    # Determine if paused for review
    snapshot = graph.get_state(config)
    is_interrupted = bool(snapshot.tasks and any(
        hasattr(t, "interrupts") and t.interrupts for t in snapshot.tasks
    ))

    status = "review" if is_interrupted else result.get("status", "completed")

    return {
        "thread_id": thread_id,
        "status": status,
        "document_id": result.get("document_id", ""),
        "review_items": result.get("review_items", []) if is_interrupted else [],
        "ingestion_summary": result.get("ingestion_summary", {}),
    }


@router.get("/pipeline/{thread_id}/status")
async def get_pipeline_status(thread_id: str):
    """Get the current pipeline state for a thread."""
    graph, _ = _get_pipeline()
    config = {"configurable": {"thread_id": thread_id}}

    snapshot = graph.get_state(config)
    if not snapshot or not snapshot.values:
        raise HTTPException(status_code=404, detail="Thread not found")

    values = snapshot.values
    is_interrupted = bool(snapshot.tasks and any(
        hasattr(t, "interrupts") and t.interrupts for t in snapshot.tasks
    ))

    return {
        "thread_id": thread_id,
        "status": "review" if is_interrupted else values.get("status", "unknown"),
        "document_id": values.get("document_id", ""),
        "review_items": values.get("review_items", []) if is_interrupted else [],
        "ingestion_summary": values.get("ingestion_summary", {}),
        "warnings": values.get("mapped_result", {}).get("warnings", []),
    }


@router.post("/pipeline/{thread_id}/review")
async def submit_review(thread_id: str, body: ReviewSubmission):
    """Submit human review decisions and resume the pipeline."""
    graph, _ = _get_pipeline()
    config = {"configurable": {"thread_id": thread_id}}

    # Resume with human decisions
    result = None
    for event in graph.stream(
        Command(resume=body.decisions), config, stream_mode="values"
    ):
        result = event

    return {
        "thread_id": thread_id,
        "status": result.get("status", "completed") if result else "unknown",
        "ingestion_summary": result.get("ingestion_summary", {}) if result else {},
    }


@router.post("/query")
async def query_graph(body: QueryRequest):
    """Ask a natural language question via Graph RAG."""
    chain = _get_rag_chain()
    result = rag_ask(chain, body.question)
    return result


@router.get("/graph/stats")
async def graph_stats():
    """Get basic graph statistics."""
    from app.graph_db.neo4j_client import Neo4jClient

    client = Neo4jClient()
    try:
        node_count = client.query("MATCH (n) RETURN count(n) AS count")[0]["count"]
        rel_count = client.query("MATCH ()-[r]->() RETURN count(r) AS count")[0]["count"]
        labels = client.query(
            "CALL db.labels() YIELD label RETURN collect(label) AS labels"
        )[0]["labels"]
        rel_types = client.query(
            "CALL db.relationshipTypes() YIELD relationshipType "
            "RETURN collect(relationshipType) AS types"
        )[0]["types"]
        return {
            "total_nodes": node_count,
            "total_relationships": rel_count,
            "node_labels": labels,
            "relationship_types": rel_types,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Neo4j unavailable: {e}")
