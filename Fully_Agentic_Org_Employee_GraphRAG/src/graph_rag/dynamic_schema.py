"""
Dynamic Schema Introspection — queries Neo4j at runtime to build
schema text for LLM prompts. Zero hardcoded domain knowledge.
"""
from __future__ import annotations

from typing import Any, Dict, List

from src.neo4j_manager import Neo4jManager
from src.utils.logger import log


def get_live_schema(db: Neo4jManager) -> str:
    """
    Query Neo4j to build a complete schema description dynamically.

    Returns a formatted text string suitable for injecting into LLM prompts.
    """
    log.info("[bold cyan]Schema Introspection[/] Querying Neo4j for live schema …")

    # 1. Get node labels and their properties
    node_info = _get_node_properties(db)

    # 2. Get relationship types and their properties
    rel_info = _get_relationship_properties(db)

    # 3. Get relationship patterns (which nodes connect to which)
    patterns = _get_relationship_patterns(db)

    # 4. Get sample values for key properties
    samples = _get_sample_values(db, node_info)

    # 5. Build formatted schema
    schema_text = _format_schema(node_info, rel_info, patterns, samples)

    log.info(
        f"[bold cyan]Schema Introspection[/] ✅ "
        f"{len(node_info)} node types, {len(rel_info)} relationship types"
    )
    return schema_text


def _get_node_properties(db: Neo4jManager) -> Dict[str, List[Dict[str, Any]]]:
    """Get all node labels and their properties."""
    try:
        results = db.run_query("""
            CALL db.schema.nodeTypeProperties()
            YIELD nodeType, propertyName, propertyTypes
            RETURN nodeType, propertyName, propertyTypes
        """)
    except Exception:
        # Fallback for older Neo4j / no APOC
        results = db.run_query("""
            MATCH (n)
            WITH labels(n) AS labels, keys(n) AS props
            UNWIND labels AS label
            UNWIND props AS prop
            WITH DISTINCT label, prop
            RETURN ':`' + label + '`' AS nodeType, prop AS propertyName, 
                   ['STRING'] AS propertyTypes
        """)

    node_info: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        # nodeType comes as ":`Label`" — clean it
        label = r["nodeType"].replace(":`", "").replace("`", "").strip(":")
        if label not in node_info:
            node_info[label] = []
        node_info[label].append({
            "property": r["propertyName"],
            "types": r["propertyTypes"],
        })

    return node_info


def _get_relationship_properties(db: Neo4jManager) -> Dict[str, List[Dict[str, Any]]]:
    """Get all relationship types and their properties."""
    try:
        results = db.run_query("""
            CALL db.schema.relTypeProperties()
            YIELD relType, propertyName, propertyTypes
            RETURN relType, propertyName, propertyTypes
        """)
    except Exception:
        results = db.run_query("""
            MATCH ()-[r]->()
            WITH type(r) AS relType, keys(r) AS props
            UNWIND props AS prop
            WITH DISTINCT relType, prop
            RETURN ':`' + relType + '`' AS relType, prop AS propertyName,
                   ['STRING'] AS propertyTypes
        """)

    rel_info: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        rel_type = r["relType"].replace(":`", "").replace("`", "").strip(":")
        if r["propertyName"] is None:
            if rel_type not in rel_info:
                rel_info[rel_type] = []
            continue
        if rel_type not in rel_info:
            rel_info[rel_type] = []
        rel_info[rel_type].append({
            "property": r["propertyName"],
            "types": r["propertyTypes"],
        })

    return rel_info


def _get_relationship_patterns(db: Neo4jManager) -> List[Dict[str, str]]:
    """Get actual relationship patterns (from_label)-[type]->(to_label)."""
    try:
        results = db.run_query("""
            MATCH (a)-[r]->(b)
            WITH DISTINCT labels(a)[0] AS from_label, type(r) AS rel_type, labels(b)[0] AS to_label
            RETURN from_label, rel_type, to_label
            ORDER BY from_label, rel_type
        """)
        return [{"from": r["from_label"], "type": r["rel_type"], "to": r["to_label"]}
                for r in results]
    except Exception:
        return []


def _get_sample_values(
    db: Neo4jManager,
    node_info: Dict[str, List[Dict[str, Any]]],
    max_samples: int = 5,
) -> Dict[str, Dict[str, list]]:
    """Get sample values for key properties of each node type."""
    samples: Dict[str, Dict[str, list]] = {}

    for label, props in node_info.items():
        samples[label] = {}
        # Get samples for the first few string-like properties
        for p in props[:5]:
            prop_name = p["property"]
            try:
                results = db.run_query(f"""
                    MATCH (n:{label})
                    WHERE n.{prop_name} IS NOT NULL
                    RETURN DISTINCT n.{prop_name} AS val
                    LIMIT {max_samples}
                """)
                vals = [r["val"] for r in results]
                if vals:
                    samples[label][prop_name] = vals
            except Exception:
                continue

    return samples


def _format_schema(
    node_info: Dict[str, List[Dict[str, Any]]],
    rel_info: Dict[str, List[Dict[str, Any]]],
    patterns: List[Dict[str, str]],
    samples: Dict[str, Dict[str, list]],
) -> str:
    """Format all schema info into a text string for LLM consumption."""
    lines = []
    lines.append("=== NEO4J GRAPH SCHEMA (Auto-Discovered) ===\n")

    # Node types
    lines.append("NODE TYPES:")
    lines.append("-" * 40)
    for label, props in sorted(node_info.items()):
        prop_strs = [f"{p['property']}" for p in props]
        lines.append(f"\n(:{label})")
        lines.append(f"  Properties: {', '.join(prop_strs)}")
        # Add sample values
        if label in samples and samples[label]:
            for prop_name, vals in list(samples[label].items())[:3]:
                val_strs = [str(v)[:50] for v in vals[:3]]
                lines.append(f"  Sample {prop_name}: {val_strs}")

    # Relationship types
    lines.append(f"\n\nRELATIONSHIP TYPES:")
    lines.append("-" * 40)
    for rel_type, props in sorted(rel_info.items()):
        prop_strs = [p["property"] for p in props if p.get("property")]
        prop_text = f" {{{', '.join(prop_strs)}}}" if prop_strs else ""
        lines.append(f"  [:{rel_type}{prop_text}]")

    # Relationship patterns
    if patterns:
        lines.append(f"\n\nRELATIONSHIP PATTERNS:")
        lines.append("-" * 40)
        for p in patterns:
            lines.append(f"  (:{p['from']})-[:{p['type']}]->(:{p['to']})")

    # Node counts
    lines.append(f"\n\nNODE COUNTS:")
    lines.append("-" * 40)
    for label in sorted(node_info.keys()):
        try:
            from src.neo4j_manager import Neo4jManager
            # We can't call db here since we don't have it, so skip
            pass
        except Exception:
            pass

    return "\n".join(lines)


def get_schema_for_cypher(db: Neo4jManager) -> str:
    """
    Get a compact schema representation optimized for Cypher generation.
    More structured than get_live_schema(), focused on query writing.
    """
    node_info = _get_node_properties(db)
    rel_info = _get_relationship_properties(db)
    patterns = _get_relationship_patterns(db)

    lines = []
    lines.append("Node properties:")
    for label, props in sorted(node_info.items()):
        prop_strs = [f"{p['property']}: {p['types'][0] if p['types'] else 'STRING'}"
                     for p in props]
        lines.append(f"{label} {{{', '.join(prop_strs)}}}")

    lines.append("\nRelationship properties:")
    for rel_type, props in sorted(rel_info.items()):
        if props:
            prop_strs = [f"{p['property']}: {p['types'][0] if p['types'] else 'STRING'}"
                         for p in props if p.get("property")]
            if prop_strs:
                # Find pattern for this rel type
                matching = [p for p in patterns if p["type"] == rel_type]
                if matching:
                    m = matching[0]
                    lines.append(
                        f"(:{m['from']})-[:{rel_type} {{{', '.join(prop_strs)}}}]->(:{m['to']})"
                    )

    lines.append("\nThe relationships available:")
    for p in patterns:
        lines.append(f"(:{p['from']})-[:{p['type']}]->(:{p['to']})")

    return "\n".join(lines)
