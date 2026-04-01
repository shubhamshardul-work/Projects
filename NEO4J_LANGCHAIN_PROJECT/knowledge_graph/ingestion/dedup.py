"""
Document deduplication utilities.
Uses content hashing to detect already-ingested documents.
"""

import hashlib


def get_document_hash(file_path: str) -> str:
    """Generate MD5 hash of file content for deduplication."""
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def is_already_ingested(doc_hash: str, graph) -> bool:
    """Check Neo4j for existing document with same hash."""
    result = graph.query(
        "MATCH (d:Document {content_hash: $hash}) RETURN count(d) AS cnt",
        params={"hash": doc_hash}
    )
    return result[0]["cnt"] > 0
