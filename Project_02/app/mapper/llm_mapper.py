"""
LLM-based mapper: Diffbot output → canonical ontology using structured LLM extraction.
Uses LangChain ChatOpenAI with Pydantic structured output.
"""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.config import MAPPED_DIR
from app.llm_factory import get_llm
from app.models.ontology import (
    NodeType,
    RelationshipType,
    NODE_PROPERTY_SCHEMA,
)
from app.models.schemas import (
    DocumentExtractionResult,
    GraphNode,
    GraphRelationship,
)
from app.mapper.entity_resolver import deduplicate_nodes
from app.mapper.rule_mapper import classify_document

# ---------------------------------------------------------------------------
# Pydantic models for LLM structured output
# ---------------------------------------------------------------------------


class LLMNodeMapping(BaseModel):
    """A single entity mapped by the LLM."""

    original_name: str = Field(description="The entity name from Diffbot")
    node_type: str = Field(description="Canonical node type from the ontology")
    node_id: str = Field(description="Unique ID for this node")
    properties: dict = Field(default_factory=dict, description="Properties matching the ontology schema")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score for this mapping")


class LLMRelMapping(BaseModel):
    """A single relationship mapped by the LLM."""

    from_id: str
    from_type: str
    to_id: str
    to_type: str
    relationship_type: str
    confidence: float = Field(ge=0.0, le=1.0)


class LLMMapperOutput(BaseModel):
    """Full structured output from the LLM mapper for one section."""

    nodes: list[LLMNodeMapping] = Field(default_factory=list)
    relationships: list[LLMRelMapping] = Field(default_factory=list)
    unmapped: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_NODE_TYPES_STR = ", ".join(nt.value for nt in NodeType)
_REL_TYPES_STR = ", ".join(rt.value for rt in RelationshipType)
_SCHEMA_STR = json.dumps(
    {nt.value: v for nt, v in NODE_PROPERTY_SCHEMA.items()}, indent=2
)

SYSTEM_PROMPT = f"""\
You are an entity-mapping agent for a contract intelligence knowledge graph.

Given Diffbot extraction results from a contract document section, map each
entity to the correct canonical node type and extract its properties.

CANONICAL NODE TYPES: {_NODE_TYPES_STR}

CANONICAL RELATIONSHIP TYPES: {_REL_TYPES_STR}

PROPERTY SCHEMAS (per node type):
{_SCHEMA_STR}

Rules:
- Only use canonical types from the lists above.
- If an entity does not fit any type, put it in the "unmapped" list.
- Assign a confidence score (0.0-1.0) to each mapping.
- For relationships, use canonical types with correct direction.
- Use the section heading and document type as context.
- Generate unique node IDs using the pattern: {{id_prefix}}{{NodeType}}-{{short_name}}
"""

HUMAN_TEMPLATE = """\
Document type: {document_type}
Section heading: {section_heading}
ID prefix: {id_prefix}

Diffbot entities:
{entities_json}

Diffbot relationships (entity-to-entity facts):
{relationships_json}

Diffbot properties (entity-to-literal facts):
{properties_json}

Map these to the canonical ontology. Return structured output.
"""


import logging
import time

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_SECONDS = [5, 10, 20]


def map_section_with_llm(
    entities: list[dict],
    relationships: list[dict],
    section_heading: str,
    document_type: str,
    id_prefix: str,
    properties: list[dict] | None = None,
) -> LLMMapperOutput:
    """
    Map one section's Diffbot output using the LLM.

    Implements retry-with-backoff: on 429/rate-limit errors, waits and
    retries with a fresh LLM instance (which rotates to the next API key
    via the round-robin pool in llm_factory).
    """
    from langchain_core.messages import SystemMessage

    prompt = ChatPromptTemplate.from_messages(
        [SystemMessage(content=SYSTEM_PROMPT), ("human", HUMAN_TEMPLATE)]
    )

    invoke_kwargs = {
        "document_type": document_type,
        "section_heading": section_heading,
        "id_prefix": id_prefix,
        "entities_json": json.dumps(entities, indent=2, default=str),
        "relationships_json": json.dumps(relationships, indent=2, default=str),
        "properties_json": json.dumps(properties or [], indent=2, default=str),
    }

    last_error: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            # Get a fresh LLM each attempt — rotates the API key
            llm = get_llm()
            structured_llm = llm.with_structured_output(LLMMapperOutput)
            chain = prompt | structured_llm

            result: LLMMapperOutput = chain.invoke(invoke_kwargs)
            if attempt > 0:
                logger.info(
                    "Section '%s' succeeded on attempt %d/%d",
                    section_heading, attempt + 1, _MAX_RETRIES,
                )
            return result

        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            is_rate_limit = any(
                keyword in error_str
                for keyword in ["429", "rate", "resource_exhausted", "quota", "too many"]
            )

            if is_rate_limit and attempt < _MAX_RETRIES - 1:
                wait = _BACKOFF_SECONDS[attempt]
                logger.warning(
                    "Rate limit hit for section '%s' (attempt %d/%d). "
                    "Waiting %ds before retry with next API key...",
                    section_heading, attempt + 1, _MAX_RETRIES, wait,
                )
                time.sleep(wait)
            else:
                # Non-rate-limit error, or final attempt — re-raise
                raise last_error


# ---------------------------------------------------------------------------
# Full document-level LLM mapping
# ---------------------------------------------------------------------------


def _llm_node_to_graph_node(ln: LLMNodeMapping) -> GraphNode | None:
    """Convert LLM output to our internal GraphNode model."""
    try:
        node_type = NodeType(ln.node_type)
    except ValueError:
        return None
    return GraphNode(
        type=node_type,
        id=ln.node_id,
        properties={**ln.properties, "name": ln.original_name},
        confidence=ln.confidence,
    )


def _llm_rel_to_graph_rel(lr: LLMRelMapping) -> GraphRelationship | None:
    try:
        from_type = NodeType(lr.from_type)
        to_type = NodeType(lr.to_type)
        rel_type = RelationshipType(lr.relationship_type)
    except ValueError:
        return None
    return GraphRelationship(
        from_id=lr.from_id,
        from_type=from_type,
        to_id=lr.to_id,
        to_type=to_type,
        type=rel_type,
        confidence=lr.confidence,
    )


def map_document_llm_based(
    diffbot_results: list[dict],
    document_id: str,
    file_name: str,
    source_file: str,
    text: str,
) -> DocumentExtractionResult:
    """Full LLM-based mapping pipeline for one document."""

    doc_type = classify_document(text, file_name)

    all_nodes: list[GraphNode] = []
    all_rels: list[GraphRelationship] = []
    unmapped_entities: list[dict] = []
    unmapped_rels: list[dict] = []
    warnings: list[str] = []

    for section_result in diffbot_results:
        entities = section_result.get("entities", [])
        relationships = section_result.get("relationships", [])
        section_properties = section_result.get("properties", [])
        section_heading = section_result.get("section_heading", "")

        if not entities:
            continue

        try:
            llm_output = map_section_with_llm(
                entities=entities,
                relationships=relationships,
                section_heading=section_heading,
                document_type=doc_type,
                id_prefix=f"{document_id}_",
                properties=section_properties,
            )

            for ln in llm_output.nodes:
                node = _llm_node_to_graph_node(ln)
                if node:
                    all_nodes.append(node)
                else:
                    unmapped_entities.append(
                        {"name": ln.original_name, "type": ln.node_type, "section": section_heading}
                    )

            for lr in llm_output.relationships:
                rel = _llm_rel_to_graph_rel(lr)
                if rel:
                    all_rels.append(rel)
                else:
                    unmapped_rels.append(
                        {"from": lr.from_id, "to": lr.to_id, "type": lr.relationship_type}
                    )

            unmapped_entities.extend(llm_output.unmapped)
            
            logger.info(
                "Section '%s' mapped: %d nodes, %d rels. Pacing 8s...",
                section_heading, len(llm_output.nodes), len(llm_output.relationships),
            )
            time.sleep(8)  # Rate-limit pacing (Groq free-tier: 30 RPM)

        except Exception as e:
            warnings.append(f"LLM mapper failed for section '{section_heading}': {e}")

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
            properties={"name": file_name, "title": file_name, "sourceDocument": source_file},
        )
        all_nodes.insert(0, doc_node)

    # --- Deduplicate ---
    all_nodes = deduplicate_nodes(all_nodes)

    # --- Deduplicate relationships ---
    seen_rels: set[tuple] = set()
    deduped_rels: list[GraphRelationship] = []
    for r in all_rels:
        key = (r.from_id, r.to_id, r.type)
        if key not in seen_rels:
            seen_rels.add(key)
            deduped_rels.append(r)

    if unmapped_entities:
        warnings.append(f"{len(unmapped_entities)} entities could not be mapped")
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


def save_mapped_result(
    result: DocumentExtractionResult, output_dir: str | None = None
) -> str:
    output_dir = output_dir or MAPPED_DIR
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = Path(output_dir) / f"{result.document_id}.json"
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return str(path)
