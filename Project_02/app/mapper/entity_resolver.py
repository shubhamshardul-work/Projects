"""
Fuzzy entity deduplication using rapidfuzz.
"""

from __future__ import annotations

from rapidfuzz import fuzz, process

from app.models.schemas import GraphNode


def deduplicate_nodes(
    nodes: list[GraphNode], threshold: int = 85
) -> list[GraphNode]:
    """
    Deduplicate nodes of the same type using fuzzy name matching.
    Keeps the first occurrence and merges properties from duplicates.
    """
    deduped: list[GraphNode] = []
    seen: dict[tuple, int] = {}  # (NodeType, canonical_name) → index in deduped

    for node in nodes:
        name = node.properties.get("name", node.id)
        node_type = node.type

        same_type_entries = {k: v for k, v in seen.items() if k[0] == node_type}

        if not same_type_entries:
            seen[(node_type, name)] = len(deduped)
            deduped.append(node)
            continue

        known_names = [k[1] for k in same_type_entries]
        match = process.extractOne(name, known_names, scorer=fuzz.token_sort_ratio)

        if match and match[1] >= threshold:
            canonical_name = match[0]
            idx = seen[(node_type, canonical_name)]
            existing = deduped[idx]
            # Merge properties — existing wins on conflict
            for k, v in node.properties.items():
                if k not in existing.properties or not existing.properties[k]:
                    existing.properties[k] = v
        else:
            seen[(node_type, name)] = len(deduped)
            deduped.append(node)

    return deduped
