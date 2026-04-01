"""
Stage A: Diffbot NLP extraction wrapper.
Uses DiffbotGraphTransformer to extract entities and relationships from text chunks.
"""

from langchain_experimental.graph_transformers.diffbot import DiffbotGraphTransformer
from langchain_core.documents import Document
from langchain_community.graphs.graph_document import GraphDocument
from typing import List
import time


def create_diffbot_transformer(api_token: str) -> DiffbotGraphTransformer:
    """
    Initialise DiffbotGraphTransformer.
    Note: DiffbotGraphTransformer extracts using Diffbot's own schema.
    Entities will be generic types: Person, Organization, etc.
    This is intentional — schema enforcement happens in Stage B.
    """
    return DiffbotGraphTransformer(diffbot_api_key=api_token)


def extract_with_diffbot(
    chunks: List[Document],
    transformer: DiffbotGraphTransformer,
    batch_size: int = 5,
    retry_limit: int = 3
) -> List[GraphDocument]:
    """
    Run DiffbotGraphTransformer on document chunks.
    Processes in small batches to respect API rate limits.
    Returns list of GraphDocument objects with Diffbot's extracted nodes and relationships.
    """
    all_graph_docs = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        for attempt in range(retry_limit):
            try:
                graph_docs = transformer.convert_to_graph_documents(batch)
                all_graph_docs.extend(graph_docs)
                time.sleep(0.5)  # Respect rate limits
                break
            except Exception as e:
                if attempt == retry_limit - 1:
                    print(f"Diffbot extraction failed after {retry_limit} attempts: {e}")
                else:
                    time.sleep(2 ** attempt)  # Exponential backoff

    return all_graph_docs
