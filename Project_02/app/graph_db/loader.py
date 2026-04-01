"""
Load validated DocumentExtractionResult into Neo4j via MERGE-based Cypher.
"""

from __future__ import annotations

from app.graph_db.neo4j_client import Neo4jClient
from app.models.schemas import DocumentExtractionResult, GraphNode, GraphRelationship


def _build_merge_node_query(node: GraphNode) -> tuple[str, dict]:
    label = node.neo4j_label()
    props = {**node.properties, "id": node.id}
    set_clauses = ", ".join(f"n.`{k}` = ${k}" for k in props)
    query = f"MERGE (n:{label} {{id: $id}}) SET {set_clauses}"
    return query, props


def _build_merge_rel_query(rel: GraphRelationship) -> tuple[str, dict]:
    from_label = rel.from_type.value
    to_label = rel.to_type.value
    rel_type = rel.type.value
    params: dict = {"from_id": rel.from_id, "to_id": rel.to_id}

    query = (
        f"MATCH (a:{from_label} {{id: $from_id}}), (b:{to_label} {{id: $to_id}}) "
        f"MERGE (a)-[r:{rel_type}]->(b)"
    )

    if rel.properties:
        set_parts = ", ".join(f"r.`{k}` = ${k}" for k in rel.properties)
        query += f" SET {set_parts}"
        params.update(rel.properties)

    return query, params


def load_extraction_result(
    client: Neo4jClient, result: DocumentExtractionResult
) -> dict:
    """
    Load a full DocumentExtractionResult into Neo4j.
    Returns {document_id, nodes_created, relationships_created, errors}.
    """
    nodes_created = 0
    rels_created = 0
    errors: list[str] = []

    for node in result.nodes:
        try:
            query, params = _build_merge_node_query(node)
            client.query(query, params)
            nodes_created += 1
        except Exception as e:
            errors.append(f"Node {node.id}: {e}")

    for rel in result.relationships:
        try:
            query, params = _build_merge_rel_query(rel)
            client.query(query, params)
            rels_created += 1
        except Exception as e:
            errors.append(f"Rel {rel.from_id}->{rel.to_id}: {e}")

    return {
        "document_id": result.document_id,
        "nodes_created": nodes_created,
        "relationships_created": rels_created,
        "errors": errors,
    }
