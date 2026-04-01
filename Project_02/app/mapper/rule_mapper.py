"""
Rule-based mapper: Diffbot output → canonical ontology.
No LLM calls — pure regex, keyword heuristics, and section context.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.models.ontology import NodeType, NODE_PROPERTY_SCHEMA
from app.models.schemas import (
    DocumentExtractionResult,
    GraphNode,
    GraphRelationship,
)
from app.mapper.entity_resolver import deduplicate_nodes
from app.mapper.relationship_builder import (
    map_diffbot_relationship,
    infer_structural_relationships,
)
from app.config import MAPPED_DIR

# ---------------------------------------------------------------------------
# Document classification
# ---------------------------------------------------------------------------

DOC_TYPE_PATTERNS: dict[str, list[str]] = {
    "MSA": [
        r"master\s+service[s]?\s+agreement",
        r"master\s+agreement",
        r"\bMSA\b",
    ],
    "SOW": [
        r"statement\s+of\s+work",
        r"\bSOW\b",
        r"scope\s+of\s+work",
    ],
    "Amendment": [
        r"amendment\s+(no\.?|number|#)?\s*\d+",
        r"contract\s+amendment",
        r"modification\s+agreement",
    ],
    "ChangeRequest": [
        r"change\s+(request|order|notice)",
        r"\bCR[\s\-]?\d+",
        r"\bCO[\s\-]?\d+",
    ],
    "SLA": [
        r"service\s+level\s+agreement",
        r"\bSLA\b",
        r"service\s+level[s]?\s+schedule",
    ],
    "PricingExhibit": [
        r"pricing\s+(exhibit|schedule|appendix)",
        r"rate\s+card",
        r"fee\s+schedule",
    ],
}


def classify_document(text: str, file_name: str = "") -> str:
    """Classify a contract document by scanning first 2000 chars + filename."""
    search_text = (file_name + " " + text[:2000]).lower()
    scores: dict[str, int] = {}
    for doc_type, patterns in DOC_TYPE_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, search_text, re.IGNORECASE))
        if score > 0:
            scores[doc_type] = score
    return max(scores, key=scores.get) if scores else "Unknown"


# ---------------------------------------------------------------------------
# Entity mapping rules
# ---------------------------------------------------------------------------

# (diffbot_type, keyword_patterns_in_name) → NodeType
ENTITY_MAPPING_RULES: list[tuple[str, list[str], NodeType]] = [
    ("Organization", [r"client", r"customer", r"buyer"], NodeType.CLIENT),
    (
        "Organization",
        [r"inc\.", r"ltd", r"llc", r"gmbh", r"corp", r"limited", r"s\.?a\.?"],
        NodeType.LEGAL_ENTITY,
    ),
    ("Organization", [], NodeType.LEGAL_ENTITY),
    ("Location", [], NodeType.LOCATION),
    ("Administrative Area", [], NodeType.LOCATION),
    (
        "Person",
        [r"manager", r"lead", r"director", r"analyst", r"architect", r"consultant"],
        NodeType.RESOURCE_ROLE,
    ),
]

# Diffbot entity types that should NOT become graph nodes — they are
# property values, not entities in our ontology.
SKIP_ENTITY_TYPES: set[str] = {
    "Date", "Number", "Currency", "Percentage",
    "Job Title", "Cause Of Death",
}

# Section heading keywords → likely node type for Misc entities
SECTION_ENTITY_HINTS: dict[str, NodeType] = {
    "deliverable": NodeType.DELIVERABLE,
    "milestone": NodeType.MILESTONE,
    "service level": NodeType.SLA,
    "sla": NodeType.SLA,
    "kpi": NodeType.KPI,
    "pricing": NodeType.PRICING_MODEL,
    "resource": NodeType.RESOURCE_ROLE,
    "scope": NodeType.DELIVERABLE,
    "schedule": NodeType.MILESTONE,
}

# ---------------------------------------------------------------------------
# Diffbot property name → our ontology property key
# Diffbot fact properties (e.g. "date of death", "employee or member of")
# are mapped to the flat property keys used in NODE_PROPERTY_SCHEMA.
# ---------------------------------------------------------------------------

DIFFBOT_PROPERTY_TO_ONTOLOGY: dict[str, str] = {
    # Dates
    "date of founding": "effectiveDate",
    "start date": "startDate",
    "end date": "endDate",
    "date signed": "effectiveDate",
    "effective date": "effectiveDate",
    "expiry date": "expiryDate",
    "termination date": "expiryDate",
    "due date": "dueDate",
    # Monetary
    "total value": "value",
    "contract value": "value",
    "amount": "value",
    "payment amount": "paymentAmount",
    "rate": "rate",
    "price": "rateCard",
    # Identifiers
    "amendment number": "amendmentNumber",
    "section number": "sectionNumber",
    "clause number": "clauseNumber",
    "version number": "versionNumber",
    # Descriptions
    "description": "description",
    "title": "title",
    "status": "status",
    "category": "category",
    # Location / Org
    "headquarters": "headquarters",
    "jurisdiction": "jurisdiction",
    "country": "country",
    "city": "city",
    "address": "address",
    "industry": "industry",
    "region": "region",
    # People
    "employee or member of": "_skip",   # handled as relationship, not property
    "nationality": "_skip",
    "gender": "_skip",
}


def map_diffbot_entity_to_node(
    entity: dict,
    section_heading: str = "",
    document_type: str = "",
    id_prefix: str = "",
    fact_properties: dict[str, list[dict]] | None = None,
) -> GraphNode | None:
    """Map a single Diffbot entity to a canonical GraphNode or return None.

    ``fact_properties`` is a dict keyed by lowercase entity name, with a list
    of {property_name, value} dicts extracted from Diffbot facts.
    """
    diffbot_type = entity.get("type", "Misc")
    name = entity.get("name", "").strip()
    if not name:
        return None

    # Skip types that are property values, not graph entities
    if diffbot_type in SKIP_ENTITY_TYPES:
        return None

    target_type: NodeType | None = None

    # Rule-based mapping
    for rule_diffbot_type, patterns, node_type in ENTITY_MAPPING_RULES:
        if diffbot_type.lower() != rule_diffbot_type.lower():
            continue
        if not patterns:
            target_type = node_type
        else:
            for p in patterns:
                if re.search(p, name, re.IGNORECASE):
                    target_type = node_type
                    break
        if target_type:
            break

    # Fallback: section context for Misc entities
    if target_type is None and diffbot_type == "Misc":
        heading_lower = section_heading.lower()
        for keyword, node_type in SECTION_ENTITY_HINTS.items():
            if keyword in heading_lower:
                target_type = node_type
                break

    if target_type is None:
        return None

    node_id = f"{id_prefix}{target_type.value}-{name[:40].replace(' ', '_')}"
    properties: dict = {"name": name}

    # Map Diffbot fact-properties into ontology properties
    allowed = set(
        NODE_PROPERTY_SCHEMA.get(target_type, {}).get("required", [])
        + NODE_PROPERTY_SCHEMA.get(target_type, {}).get("optional", [])
    )
    if fact_properties:
        for prop in fact_properties.get(name.lower(), []):
            mapped_key = DIFFBOT_PROPERTY_TO_ONTOLOGY.get(
                prop["property_name"].lower()
            )
            if mapped_key and mapped_key in allowed:
                properties[mapped_key] = prop["value"]

    # Also pull confidence and salience from entity for diagnostics
    confidence = entity.get("confidence", 1.0) * entity.get("salience", 1.0)

    return GraphNode(
        type=target_type,
        id=node_id,
        properties=properties,
        confidence=min(max(confidence, 0.0), 1.0),
    )


# ---------------------------------------------------------------------------
# Full document-level rule mapping
# ---------------------------------------------------------------------------

def _build_node_lookup(nodes: list[GraphNode]) -> dict[str, GraphNode]:
    lookup: dict[str, GraphNode] = {}
    for n in nodes:
        name = n.properties.get("name", "").lower()
        if name:
            lookup[name] = n
    return lookup


def map_document_rule_based(
    diffbot_results: list[dict],
    document_id: str,
    file_name: str,
    source_file: str,
    text: str,
) -> DocumentExtractionResult:
    """Full rule-based mapping pipeline for one document."""

    doc_type = classify_document(text, file_name)

    # --- Build per-entity property dict from Diffbot facts/properties ---
    fact_properties: dict[str, list[dict]] = {}
    for section_result in diffbot_results:
        for prop in section_result.get("properties", []):
            key = prop.get("entity_name", "").lower()
            if key:
                fact_properties.setdefault(key, []).append(prop)

    # --- Map entities ---
    all_nodes: list[GraphNode] = []
    unmapped_entities: list[dict] = []

    for section_result in diffbot_results:
        section_heading = section_result.get("section_heading", "")
        for entity in section_result.get("entities", []):
            node = map_diffbot_entity_to_node(
                entity=entity,
                section_heading=section_heading,
                document_type=doc_type,
                id_prefix=f"{document_id}_",
                fact_properties=fact_properties,
            )
            if node:
                all_nodes.append(node)
            else:
                unmapped_entities.append(
                    {
                        "name": entity.get("name"),
                        "type": entity.get("type"),
                        "section": section_heading,
                    }
                )

    # --- Create document-level node ---
    doc_node_type_map = {
        "SOW": NodeType.SOW,
        "MSA": NodeType.MSA,
        "Amendment": NodeType.AMENDMENT,
        "ChangeRequest": NodeType.CHANGE_REQUEST,
        "SLA": NodeType.SLA,
    }
    doc_node_type = doc_node_type_map.get(doc_type)
    if doc_node_type:
        doc_node = GraphNode(
            type=doc_node_type,
            id=f"{document_id}_{doc_type}",
            properties={
                "name": file_name,
                "title": file_name,
                "sourceDocument": source_file,
            },
        )
        all_nodes.insert(0, doc_node)

    # --- Deduplicate ---
    all_nodes = deduplicate_nodes(all_nodes)

    # --- Map Diffbot relationships ---
    node_lookup = _build_node_lookup(all_nodes)
    all_rels: list[GraphRelationship] = []
    unmapped_rels: list[dict] = []

    for section_result in diffbot_results:
        for rel in section_result.get("relationships", []):
            mapped = map_diffbot_relationship(rel, node_lookup)
            if mapped:
                all_rels.append(mapped)
            else:
                unmapped_rels.append(rel)

    # --- Infer structural relationships ---
    structural_rels = infer_structural_relationships(all_nodes, doc_type)
    all_rels.extend(structural_rels)

    # --- Deduplicate relationships ---
    seen_rels: set[tuple] = set()
    deduped_rels: list[GraphRelationship] = []
    for r in all_rels:
        key = (r.from_id, r.to_id, r.type)
        if key not in seen_rels:
            seen_rels.add(key)
            deduped_rels.append(r)

    # --- Warnings ---
    warnings: list[str] = []
    if unmapped_entities:
        warnings.append(
            f"{len(unmapped_entities)} entities could not be mapped to the ontology"
        )
    if unmapped_rels:
        warnings.append(f"{len(unmapped_rels)} relationships could not be mapped")
    if doc_type == "Unknown":
        warnings.append("Document type could not be determined")

    return DocumentExtractionResult(
        document_id=document_id,
        document_type=doc_type,
        source_file=source_file,
        nodes=all_nodes,
        relationships=deduped_rels,
        unmapped_entities=unmapped_entities,
        unmapped_relationships=unmapped_rels,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_mapped_result(
    result: DocumentExtractionResult, output_dir: str | None = None
) -> str:
    """Persist the canonical JSON for auditing."""
    output_dir = output_dir or MAPPED_DIR
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = Path(output_dir) / f"{result.document_id}.json"
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return str(path)
