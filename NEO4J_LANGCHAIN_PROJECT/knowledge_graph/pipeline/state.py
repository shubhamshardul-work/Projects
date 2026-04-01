"""
LangGraph state definition for the pipeline.
Defines the TypedDict that flows through all pipeline nodes.
"""

from typing import TypedDict, List, Optional, Any
from langchain_core.documents import Document
from langchain_community.graphs.graph_document import GraphDocument
from extraction.schema_extractor import GraphExtraction


class GraphState(TypedDict):
    """State flowing through the LangGraph pipeline."""

    # Input
    file_path: str
    doc_hash: str

    # After ingestion
    raw_documents: List[Document]
    doc_type: str
    chunks: List[Document]

    # After Diffbot
    diffbot_graph_docs: List[GraphDocument]

    # After bridge
    enriched_documents: List[Document]

    # After structured output extraction
    schema_extractions: List[GraphExtraction]

    # After resolution
    resolved_extractions: List[GraphExtraction]

    # Write results
    write_stats: dict

    # Control flags
    is_duplicate: bool
    needs_review: bool
    retry_count: int
    errors: List[str]
