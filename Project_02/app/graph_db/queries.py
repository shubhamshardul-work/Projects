"""
Index creation and common Cypher query templates.
"""

from __future__ import annotations

from app.models.ontology import NodeType
from app.graph_db.neo4j_client import Neo4jClient

# Auto-generate index statements for every node type
INDEX_QUERIES = [
    f"CREATE INDEX IF NOT EXISTS FOR (n:{nt.value}) ON (n.id)" for nt in NodeType
]


COMMON_QUERIES: dict[str, str] = {
    "all_sows_for_client": (
        "MATCH (c:Client)-[:HAS_ACCOUNT]->(a:Account)-[:HAS_ENGAGEMENT]->(e:Engagement)"
        "-[:HAS_PROJECT]->(p:Project)-[:GOVERNED_BY]->(con:Contract)-[:HAS_SOW]->(s:SOW) "
        "WHERE c.name = $client_name RETURN s"
    ),
    "clauses_modified_by_amendment": (
        "MATCH (a:Amendment)-[:MODIFIES]->(cl:Clause)<-[:HAS_CLAUSE]-(s:SOW) "
        "WHERE a.id = $amendment_id RETURN a, cl, s"
    ),
    "deliverables_for_sow": (
        "MATCH (s:SOW)-[:HAS_DELIVERABLE]->(d:Deliverable) "
        "WHERE s.id = $sow_id RETURN d"
    ),
    "amendment_lineage": (
        "MATCH path = (s:SOW)-[:HAS_CLAUSE]->(cl:Clause)"
        "-[:MODIFIED_BY|SUPERSEDED_BY*1..5]->(target) "
        "WHERE s.id = $sow_id RETURN path"
    ),
    "full_contract_tree": (
        "MATCH path = (c:Contract)-[*1..4]->(child) "
        "WHERE c.id = $contract_id RETURN path"
    ),
}


def create_indexes(client: Neo4jClient) -> int:
    """Create all indexes. Returns count of statements executed."""
    for q in INDEX_QUERIES:
        client.query(q)
    return len(INDEX_QUERIES)
