"""
LangGraph node functions for the knowledge graph pipeline.
Each function takes a GraphState, performs work, and returns updated state.
"""

from pipeline.state import GraphState
from ingestion.loaders import load_document
from ingestion.chunker import chunk_document
from ingestion.classifier import classify_document
from ingestion.dedup import get_document_hash, is_already_ingested
from extraction.diffbot_extractor import create_diffbot_transformer, extract_with_diffbot
from extraction.bridge import graphdocs_to_enriched_documents
from extraction.schema_extractor import create_schema_extractor, extract_with_structured_output
from graph.neo4j_writer import (
    get_neo4j_graph, write_extractions_to_neo4j,
    write_chunk_embeddings, write_source_provenance
)
from graph.entity_resolver import resolve_entities
from config.settings import LLM_MODEL, EMBEDDING_MODEL, DIFFBOT_API_TOKEN
from config.llm_factory import get_llm, get_embeddings

# Initialise shared resources once
llm = get_llm(temperature=0.0)
diffbot_transformer = create_diffbot_transformer(DIFFBOT_API_TOKEN)
schema_extractor = create_schema_extractor()
graph = get_neo4j_graph()
embeddings = get_embeddings()


def ingest_node(state: GraphState) -> GraphState:
    """Load, classify, deduplicate, and chunk the source document."""
    file_path = state["file_path"]
    doc_hash = get_document_hash(file_path)
    state["doc_hash"] = doc_hash

    if is_already_ingested(doc_hash, graph):
        state["is_duplicate"] = True
        return state

    raw_docs = load_document(file_path)
    doc_type = classify_document(raw_docs[0], llm)
    chunks = []
    for doc in raw_docs:
        chunks.extend(chunk_document(doc))

    state["raw_documents"] = raw_docs
    state["doc_type"] = doc_type
    state["chunks"] = chunks
    state["is_duplicate"] = False
    return state


def diffbot_extraction_node(state: GraphState) -> GraphState:
    """Run DiffbotGraphTransformer on chunks — Stage A extraction."""
    graph_docs = extract_with_diffbot(
        state["chunks"],
        diffbot_transformer,
        retry_limit=state.get("retry_count", 0) + 1
    )
    state["diffbot_graph_docs"] = graph_docs
    return state


def bridge_node(state: GraphState) -> GraphState:
    """Convert Diffbot GraphDocuments to enriched Documents for structured output extraction."""
    enriched = graphdocs_to_enriched_documents(state["diffbot_graph_docs"])
    state["enriched_documents"] = enriched
    return state


def llm_schema_node(state: GraphState) -> GraphState:
    """Run structured output extraction — Stage B schema enforcement."""
    extractions = extract_with_structured_output(
        state["enriched_documents"],
        schema_extractor
    )
    # Flag for review if extraction yield is very low
    total_nodes = sum(len(ext.nodes) for ext in extractions)
    state["schema_extractions"] = extractions
    state["needs_review"] = total_nodes == 0
    return state


def entity_resolution_node(state: GraphState) -> GraphState:
    """Deduplicate and merge entities across documents."""
    resolved = resolve_entities(state["schema_extractions"], graph)
    state["resolved_extractions"] = resolved
    return state


def neo4j_write_node(state: GraphState) -> GraphState:
    """Write resolved extractions to Neo4j with provenance."""
    # Write source provenance (Document + Chunk nodes)
    write_source_provenance(
        graph,
        state["file_path"],
        state["doc_hash"],
        state.get("doc_type", "Unknown"),
        state["chunks"]
    )
    # Write extracted entities and relationships
    stats = write_extractions_to_neo4j(graph, state["resolved_extractions"])
    # Write chunk embeddings for vector search
    write_chunk_embeddings(graph, state["chunks"], embeddings)
    state["write_stats"] = stats
    return state


def skip_node(state: GraphState) -> GraphState:
    """No-op node for duplicate documents."""
    print(f"Skipping duplicate document: {state['file_path']}")
    return state


def review_node(state: GraphState) -> GraphState:
    """Human-in-the-loop review for low-confidence extractions."""
    print(f"Document flagged for review: {state['file_path']}")
    print("Zero nodes extracted — manual review required before writing to graph.")
    # In production: send to a review queue (email, Slack, task system)
    return state
