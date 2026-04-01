"""
Relationship mapping: Diffbot generic rels → canonical types,
plus structural inference from document type + node types.
"""

from __future__ import annotations

from app.models.ontology import NodeType, RelationshipType
from app.models.schemas import GraphNode, GraphRelationship

# (from_type, to_type) → default relationship
STRUCTURAL_RELATIONSHIP_RULES: dict[tuple[NodeType, NodeType], RelationshipType] = {
    (NodeType.CLIENT, NodeType.ACCOUNT): RelationshipType.HAS_ACCOUNT,
    (NodeType.ACCOUNT, NodeType.ENGAGEMENT): RelationshipType.HAS_ENGAGEMENT,
    (NodeType.ENGAGEMENT, NodeType.PROJECT): RelationshipType.HAS_PROJECT,
    (NodeType.PROJECT, NodeType.CONTRACT): RelationshipType.GOVERNED_BY,
    (NodeType.CONTRACT, NodeType.SOW): RelationshipType.HAS_SOW,
    (NodeType.CONTRACT, NodeType.MSA): RelationshipType.GOVERNED_BY,
    (NodeType.CONTRACT, NodeType.AMENDMENT): RelationshipType.HAS_AMENDMENT,
    (NodeType.SOW, NodeType.CLAUSE): RelationshipType.HAS_CLAUSE,
    (NodeType.SOW, NodeType.SECTION): RelationshipType.HAS_SECTION,
    (NodeType.SOW, NodeType.DELIVERABLE): RelationshipType.HAS_DELIVERABLE,
    (NodeType.SOW, NodeType.MILESTONE): RelationshipType.HAS_MILESTONE,
    (NodeType.SOW, NodeType.PRICING_MODEL): RelationshipType.USES_PRICING_MODEL,
    (NodeType.SOW, NodeType.SLA): RelationshipType.HAS_SLA,
    (NodeType.SOW, NodeType.KPI): RelationshipType.HAS_KPI,
    (NodeType.DELIVERABLE, NodeType.SLA): RelationshipType.TRACKED_BY,
    (NodeType.CLAUSE, NodeType.AMENDMENT): RelationshipType.MODIFIED_BY,
    (NodeType.CLAUSE, NodeType.CLAUSE): RelationshipType.REFERS_TO,
    (NodeType.PROJECT, NodeType.RESOURCE_ROLE): RelationshipType.DELIVERED_BY,
}

# Diffbot fact property name → canonical relationship type
DIFFBOT_REL_MAPPING: dict[str, RelationshipType] = {
    "partner": RelationshipType.HAS_ACCOUNT,
    "subsidiary": RelationshipType.BELONGS_TO,
    "parent": RelationshipType.BELONGS_TO,
    "parent organization": RelationshipType.BELONGS_TO,
    "location": RelationshipType.BELONGS_TO,
    "headquarters": RelationshipType.BELONGS_TO,
    "employer": RelationshipType.DELIVERED_BY,
    "employee or member of": RelationshipType.DELIVERED_BY,
    "all locations": RelationshipType.BELONGS_TO,
    "all person locations": RelationshipType.BELONGS_TO,
}


def map_diffbot_relationship(
    diffbot_rel: dict,
    node_lookup: dict[str, GraphNode],
) -> GraphRelationship | None:
    """Map one Diffbot fact (entity→entity) to a canonical GraphRelationship.

    Diffbot facts use ``entity`` (source) and ``value`` (target) keys,
    plus a ``property`` dict with the relationship name.
    """
    # Support both old entity1/entity2 format and correct Diffbot entity/value format
    e1_ref = diffbot_rel.get("entity") or diffbot_rel.get("entity1", {})
    e2_ref = diffbot_rel.get("value") or diffbot_rel.get("entity2", {})
    e1_name = e1_ref.get("name", "").strip().lower()
    e2_name = e2_ref.get("name", "").strip().lower()
    prop_name = diffbot_rel.get("property", {}).get("name", "").strip().lower()

    node1 = node_lookup.get(e1_name)
    node2 = node_lookup.get(e2_name)
    if not node1 or not node2:
        return None

    rel_type = DIFFBOT_REL_MAPPING.get(prop_name)

    if rel_type is None:
        rel_type = STRUCTURAL_RELATIONSHIP_RULES.get((node1.type, node2.type))

    if rel_type is None:
        rel_type = STRUCTURAL_RELATIONSHIP_RULES.get((node2.type, node1.type))
        if rel_type:
            node1, node2 = node2, node1

    if rel_type is None:
        return None

    confidence = diffbot_rel.get("confidence", 1.0)

    return GraphRelationship(
        from_id=node1.id,
        from_type=node1.type,
        to_id=node2.id,
        to_type=node2.type,
        type=rel_type,
        confidence=confidence,
    )


def infer_structural_relationships(
    nodes: list[GraphNode],
    document_type: str,
) -> list[GraphRelationship]:
    """
    Infer relationships that must exist based on document type
    and the set of extracted nodes.
    """
    relationships: list[GraphRelationship] = []

    type_map = {
        "SOW": NodeType.SOW,
        "MSA": NodeType.MSA,
        "Amendment": NodeType.AMENDMENT,
    }
    primary_type = type_map.get(document_type)
    if not primary_type:
        return relationships

    doc_node = next((n for n in nodes if n.type == primary_type), None)
    if not doc_node:
        return relationships

    child_mappings: dict[NodeType, RelationshipType] = {
        NodeType.CLAUSE: RelationshipType.HAS_CLAUSE,
        NodeType.SECTION: RelationshipType.HAS_SECTION,
        NodeType.DELIVERABLE: RelationshipType.HAS_DELIVERABLE,
        NodeType.MILESTONE: RelationshipType.HAS_MILESTONE,
        NodeType.SLA: RelationshipType.HAS_SLA,
        NodeType.KPI: RelationshipType.HAS_KPI,
        NodeType.PRICING_MODEL: RelationshipType.USES_PRICING_MODEL,
    }

    for n in nodes:
        if n.id == doc_node.id:
            continue
        rel_type = child_mappings.get(n.type)
        if rel_type:
            relationships.append(
                GraphRelationship(
                    from_id=doc_node.id,
                    from_type=doc_node.type,
                    to_id=n.id,
                    to_type=n.type,
                    type=rel_type,
                )
            )

    return relationships
