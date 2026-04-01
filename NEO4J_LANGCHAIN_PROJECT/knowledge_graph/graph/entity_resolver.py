"""
Entity resolution and deduplication.
Normalises entity IDs before writing to Neo4j to prevent duplicate nodes.
"""

from extraction.schema_extractor import GraphExtraction
from langchain_neo4j import Neo4jGraph
from typing import List
import re


def normalise_name(name: str) -> str:
    """Normalise entity name for matching."""
    name = name.lower().strip()
    # Remove common legal suffixes
    suffixes = [" ltd", " limited", " inc", " llc", " pvt", " private", " corp", " corporation"]
    for suffix in suffixes:
        name = name.replace(suffix, "")
    # Remove punctuation
    name = re.sub(r"[^\w\s]", "", name)
    return name.strip()


def resolve_entities(
    extractions: List[GraphExtraction],
    graph: Neo4jGraph
) -> List[GraphExtraction]:
    """
    Pre-resolve entities before writing to Neo4j.
    Normalise node IDs so MERGE operations correctly deduplicate.
    """
    for extraction in extractions:
        for node in extraction.nodes:
            # Normalise name for consistent MERGE keys
            node.id = normalise_name(node.id)
            # Prefer canonical_id as the node key if Diffbot provided one
            if node.properties.get("canonical_id"):
                node.id = node.properties["canonical_id"]

        # Update edge source/target IDs to match normalised node IDs
        for edge in extraction.edges:
            edge.source_id = normalise_name(edge.source_id)
            edge.target_id = normalise_name(edge.target_id)

    return extractions


def merge_duplicate_nodes_in_neo4j(graph: Neo4jGraph):
    """
    Post-write APOC merge for any duplicates that slipped through.
    Requires APOC plugin enabled in Neo4j.
    """
    # Find nodes with same normalised name within the same label
    node_labels = ["Client", "Person", "Project", "SOW", "BusinessUnit"]
    for label in node_labels:
        try:
            graph.query(f"""
                MATCH (a:{label}), (b:{label})
                WHERE id(a) < id(b)
                  AND toLower(trim(a.name)) = toLower(trim(b.name))
                CALL apoc.refactor.mergeNodes([a, b], {{
                    properties: 'combine',
                    mergeRels: true
                }})
                YIELD node
                RETURN count(node) AS merged
            """)
        except Exception as e:
            print(f"Merge for {label} nodes: {e}")
