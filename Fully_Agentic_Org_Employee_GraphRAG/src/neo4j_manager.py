"""
Neo4j Manager — connection pool and query execution.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, List

from neo4j import GraphDatabase

from src.config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
from src.utils.logger import log


class Neo4jManager:
    """Thin wrapper around the Neo4j Python driver."""

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        self._uri = uri or NEO4J_URI
        self._username = username or NEO4J_USERNAME
        self._password = password or NEO4J_PASSWORD
        self._driver = None

    # ── Connection ────────────────────────────────────────────────────
    def connect(self) -> "Neo4jManager":
        """Open driver connection."""
        log.info(f"[bold blue]Neo4j[/] Connecting to {self._uri} …")
        self._driver = GraphDatabase.driver(
            self._uri,
            auth=(self._username, self._password),
        )
        # Verify connectivity
        self._driver.verify_connectivity()
        log.info("[bold blue]Neo4j[/] ✅ Connected successfully")
        return self

    def close(self) -> None:
        """Close driver connection."""
        if self._driver:
            self._driver.close()
            log.info("[bold blue]Neo4j[/] Connection closed")

    @contextmanager
    def session(self):
        """Yield a Neo4j session, auto-closing on exit."""
        if not self._driver:
            self.connect()
        sess = self._driver.session()
        try:
            yield sess
        finally:
            sess.close()

    # ── Query helpers ─────────────────────────────────────────────────
    def run_query(
        self,
        query: str,
        parameters: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results as list of dicts."""
        with self.session() as sess:
            result = sess.run(query, parameters or {})
            return [record.data() for record in result]

    def run_write(
        self,
        query: str,
        parameters: Dict[str, Any] | None = None,
    ) -> None:
        """Execute a write Cypher query inside a transaction."""
        with self.session() as sess:
            sess.execute_write(lambda tx: tx.run(query, parameters or {}))

    def run_write_batch(
        self,
        query: str,
        batch: List[Dict[str, Any]],
        batch_size: int = 500,
    ) -> int:
        """Execute a parameterised write in batches using UNWIND."""
        total = 0
        for i in range(0, len(batch), batch_size):
            chunk = batch[i : i + batch_size]
            with self.session() as sess:
                sess.execute_write(
                    lambda tx, rows=chunk: tx.run(query, {"rows": rows})
                )
            total += len(chunk)
        return total

    def clear_database(self) -> None:
        """Delete all nodes and relationships — use with caution."""
        log.info("[bold red]Neo4j[/] Clearing entire database …")
        self.run_write("MATCH (n) DETACH DELETE n")
        log.info("[bold red]Neo4j[/] Database cleared")

    def get_counts(self) -> Dict[str, int]:
        """Return node / relationship counts."""
        nodes = self.run_query("MATCH (n) RETURN count(n) AS count")[0]["count"]
        rels = self.run_query("MATCH ()-[r]->() RETURN count(r) AS count")[0]["count"]
        return {"nodes": nodes, "relationships": rels}
