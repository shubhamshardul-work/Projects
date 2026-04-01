"""
LangGraph StateGraph assembly and compilation.
Defines the pipeline DAG with conditional routing.
"""

from langgraph.graph import StateGraph, END
from pipeline.state import GraphState
from pipeline.nodes import (
    ingest_node, diffbot_extraction_node, bridge_node,
    llm_schema_node, entity_resolution_node,
    neo4j_write_node, skip_node, review_node
)


def build_pipeline() -> StateGraph:
    """Assemble the full LangGraph pipeline."""
    builder = StateGraph(GraphState)

    # Register nodes
    builder.add_node("ingest", ingest_node)
    builder.add_node("diffbot_extract", diffbot_extraction_node)
    builder.add_node("bridge", bridge_node)
    builder.add_node("llm_schema", llm_schema_node)
    builder.add_node("entity_resolution", entity_resolution_node)
    builder.add_node("neo4j_write", neo4j_write_node)
    builder.add_node("skip", skip_node)
    builder.add_node("review", review_node)

    # Entry point
    builder.set_entry_point("ingest")

    # Conditional edge: skip duplicates
    builder.add_conditional_edges(
        "ingest",
        lambda state: "skip" if state["is_duplicate"] else "diffbot_extract"
    )

    # Linear flow: diffbot → bridge → llm_schema
    builder.add_edge("diffbot_extract", "bridge")
    builder.add_edge("bridge", "llm_schema")

    # Conditional edge: route low-confidence to review
    builder.add_conditional_edges(
        "llm_schema",
        lambda state: "review" if state["needs_review"] else "entity_resolution"
    )

    # Linear flow: resolution → write → end
    builder.add_edge("entity_resolution", "neo4j_write")
    builder.add_edge("neo4j_write", END)
    builder.add_edge("skip", END)
    builder.add_edge("review", END)

    return builder.compile()
