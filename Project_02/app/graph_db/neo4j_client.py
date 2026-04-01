"""
Neo4j client using LangChain's Neo4jGraph.
Single connection object shared by ingestion and Graph RAG.
"""

from __future__ import annotations

from langchain_community.graphs import Neo4jGraph

from app.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


class Neo4jClient:
    """Thin wrapper around LangChain Neo4jGraph."""

    def __init__(self) -> None:
        self.graph = Neo4jGraph(
            url=NEO4J_URI,
            username=NEO4J_USER,
            password=NEO4J_PASSWORD,
        )

    def query(self, cypher: str, params: dict | None = None) -> list[dict]:
        """Execute a read or write Cypher query."""
        return self.graph.query(cypher, params=params or {})

    def refresh_schema(self) -> None:
        """Refresh the cached graph schema (used by RAG)."""
        self.graph.refresh_schema()

    @property
    def schema(self) -> str:
        """Return the current graph schema as text."""
        return self.graph.schema

    def verify_connectivity(self) -> bool:
        """Quick connectivity check."""
        self.query("RETURN 1 AS ok")
        return True
