"""
Neo4j write operations.
Writes structured extraction results to Neo4j using MERGE patterns for idempotent upserts.
"""

from langchain_neo4j import Neo4jGraph
from langchain_openai import OpenAIEmbeddings
from typing import List

from extraction.schema_extractor import GraphExtraction
from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD


def get_neo4j_graph() -> Neo4jGraph:
    """Create and return a Neo4jGraph connection."""
    return Neo4jGraph(
        url=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
    )


def write_extractions_to_neo4j(
    graph: Neo4jGraph,
    extractions: List[GraphExtraction],
    source_metadata: dict = None
) -> dict:
    """
    Write structured output extractions to Neo4j using MERGE patterns.

    For each extracted node, creates a node with the appropriate label and properties.
    For each extracted edge, creates a relationship between source and target nodes.
    Uses MERGE instead of CREATE for idempotent, safe upserts.
    """
    total_nodes = 0
    total_rels = 0

    for extraction in extractions:
        # Write nodes
        for node in extraction.nodes:
            # Build property SET clause dynamically
            props = {"id": node.id, **node.properties}
            set_clauses = ", ".join([f"n.{k} = ${k}" for k in props.keys()])
            query = f"MERGE (n:`{node.type}` {{id: $id}}) SET {set_clauses}"
            graph.query(query, params=props)
            total_nodes += 1

        # Write relationships
        for edge in extraction.edges:
            props = edge.properties or {}
            set_clause = ""
            if props:
                set_parts = ", ".join([f"r.{k} = ${k}" for k in props.keys()])
                set_clause = f" SET {set_parts}"
            query = f"""
                MATCH (a {{id: $source_id}}), (b {{id: $target_id}})
                MERGE (a)-[r:`{edge.type}`]->(b){set_clause}
            """
            params = {"source_id": edge.source_id, "target_id": edge.target_id, **props}
            graph.query(query, params=params)
            total_rels += 1

    return {
        "nodes_written": total_nodes,
        "relationships_written": total_rels,
        "extractions_processed": len(extractions),
    }


def write_chunk_embeddings(
    graph: Neo4jGraph,
    chunks: List,
    embeddings_model: OpenAIEmbeddings
) -> None:
    """
    Compute and store vector embeddings on :Chunk nodes.
    Required for vector similarity search and GraphRAG.
    """
    for chunk in chunks:
        embedding = embeddings_model.embed_query(chunk.page_content)
        graph.query(
            """
            MATCH (c:Chunk {chunk_id: $chunk_id})
            SET c.embedding = $embedding
            """,
            params={"chunk_id": chunk.metadata["chunk_id"], "embedding": embedding}
        )


def write_source_provenance(
    graph: Neo4jGraph,
    file_path: str,
    doc_hash: str,
    doc_type: str,
    chunks: List
) -> None:
    """
    Create :Document and :Chunk nodes for provenance tracking.
    Links chunks to their source document via PART_OF relationships.
    """
    from pathlib import Path
    from datetime import datetime

    file_name = Path(file_path).name

    # Create Document node
    graph.query(
        """
        MERGE (d:Document {content_hash: $hash})
        SET d.file_name = $file_name,
            d.file_path = $file_path,
            d.doc_type = $doc_type,
            d.ingestion_date = $ingestion_date
        """,
        params={
            "hash": doc_hash,
            "file_name": file_name,
            "file_path": file_path,
            "doc_type": doc_type,
            "ingestion_date": datetime.now().isoformat(),
        }
    )

    # Create Chunk nodes and link to Document
    for chunk in chunks:
        graph.query(
            """
            MERGE (c:Chunk {chunk_id: $chunk_id})
            SET c.text = $text,
                c.chunk_index = $chunk_index,
                c.total_chunks = $total_chunks
            WITH c
            MATCH (d:Document {content_hash: $doc_hash})
            MERGE (c)-[:PART_OF]->(d)
            """,
            params={
                "chunk_id": chunk.metadata["chunk_id"],
                "text": chunk.page_content,
                "chunk_index": chunk.metadata.get("chunk_index", 0),
                "total_chunks": chunk.metadata.get("total_chunks", 1),
                "doc_hash": doc_hash,
            }
        )
