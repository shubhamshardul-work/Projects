"""
Pydantic models for graph data validation and LangGraph pipeline state.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from app.models.ontology import NodeType, RelationshipType


# ---------------------------------------------------------------------------
# Graph data models
# ---------------------------------------------------------------------------

class GraphNode(BaseModel):
    """A single node to be written to Neo4j."""

    type: NodeType
    id: str = Field(..., min_length=1)
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    def neo4j_label(self) -> str:
        return self.type.value


class GraphRelationship(BaseModel):
    """A single relationship to be written to Neo4j."""

    from_id: str = Field(..., min_length=1)
    from_type: NodeType
    to_id: str = Field(..., min_length=1)
    to_type: NodeType
    type: RelationshipType
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class DocumentExtractionResult(BaseModel):
    """Canonical intermediate representation for one document."""

    document_id: str
    document_type: str
    source_file: str
    nodes: list[GraphNode] = Field(default_factory=list)
    relationships: list[GraphRelationship] = Field(default_factory=list)
    unmapped_entities: list[dict] = Field(default_factory=list)
    unmapped_relationships: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentRecord(BaseModel):
    """Metadata for a document in the inventory."""

    document_id: str
    file_name: str
    file_path: str
    file_type: str
    document_type: Optional[str] = None
    client_name: Optional[str] = None
    project_name: Optional[str] = None
    upload_date: Optional[str] = None
    status: str = "pending"


# ---------------------------------------------------------------------------
# Review models (for human-in-the-loop)
# ---------------------------------------------------------------------------

class ReviewItem(BaseModel):
    """A single item flagged for human review."""

    item_id: str
    item_type: str  # "node" or "relationship"
    entity_name: str
    diffbot_type: Optional[str] = None
    suggested_node_type: Optional[str] = None
    confidence: float = 0.0
    section_heading: str = ""
    context_text: str = ""
    reason: str = ""


class ReviewDecision(BaseModel):
    """A human decision on a review item."""

    item_id: str
    action: str  # "approve", "edit", "reject"
    new_node_type: Optional[str] = None
    new_properties: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# LangGraph pipeline state
# ---------------------------------------------------------------------------

class PipelineState(TypedDict, total=False):
    """The state dictionary passed between LangGraph nodes."""

    # Run metadata
    run_folder: str | None

    # Inputs
    file_path: str
    client_name: str | None
    project_name: str | None
    mapper_mode: str  # "rules" or "llm"

    # Populated by pipeline nodes
    document_id: str
    raw_text: str
    cleaned_text: str
    sections: list
    diffbot_results: list
    mapped_result: dict  # DocumentExtractionResult.model_dump()
    needs_review: bool
    review_items: list  # list of ReviewItem dicts
    human_decisions: list  # list of ReviewDecision dicts
    ingestion_summary: dict

    # Status
    status: str  # "running" | "review" | "completed" | "failed"
    error: str
