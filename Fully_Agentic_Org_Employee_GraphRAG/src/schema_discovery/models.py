"""
Pydantic Models — structured output schemas for LLM-inferred graph mappings.

These models define the contract between the Schema Discovery Agent and
the Dynamic Ingestion Engine. The LLM MUST return data conforming to
GraphMappingModel, enforced via structured output.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class PropertyMapping(BaseModel):
    """Maps a source column to a Neo4j node/relationship property."""

    column_name: str = Field(
        description="Exact column name in the source table"
    )
    property_name: str = Field(
        description="Neo4j property name (snake_case, lowercase)"
    )
    neo4j_type: str = Field(
        description="Neo4j type: STRING, INTEGER, FLOAT, DATE, BOOLEAN"
    )
    is_key: bool = Field(
        default=False,
        description="True if this property is the primary key / unique identifier",
    )


class NodeMapping(BaseModel):
    """Defines how a source table maps to a Neo4j node label."""

    label: str = Field(
        description="Neo4j node label in PascalCase (e.g., 'Employee', 'Skill')"
    )
    source_table: str = Field(
        description="Name of the sheet/CSV/table this node is sourced from"
    )
    primary_key_column: str = Field(
        description="Column in the source table used as the unique identifier"
    )
    primary_key_property: str = Field(
        description="Neo4j property name for the primary key (snake_case)"
    )
    properties: List[PropertyMapping] = Field(
        default_factory=list,
        description="List of column-to-property mappings for this node",
    )
    description: str = Field(
        default="",
        description="Short description of what this node represents",
    )


class RelationshipMapping(BaseModel):
    """Defines how source data maps to a Neo4j relationship."""

    type: str = Field(
        description="Relationship type in UPPER_SNAKE_CASE (e.g., 'HAS_SKILL', 'WORKS_IN')"
    )
    source_table: str = Field(
        description="Table containing the foreign key or junction data"
    )
    from_node_label: str = Field(
        description="Source node label (the node the relationship starts from)"
    )
    from_key_column: str = Field(
        description="Column in source_table that maps to the source node's primary key"
    )
    to_node_label: str = Field(
        description="Target node label (the node the relationship points to)"
    )
    to_key_column: str = Field(
        description="Column in source_table that maps to the target node's primary key"
    )
    properties: List[PropertyMapping] = Field(
        default_factory=list,
        description="Properties to store on the relationship (from junction table columns)",
    )
    description: str = Field(
        default="",
        description="Short description of what this relationship represents",
    )


class GraphMappingModel(BaseModel):
    """
    Complete mapping from tabular source data to a Neo4j property graph.

    This is the central contract: the Schema Discovery Agent produces it,
    the Dynamic Ingestion Engine consumes it.
    """

    nodes: List[NodeMapping] = Field(
        description="All node type mappings"
    )
    relationships: List[RelationshipMapping] = Field(
        description="All relationship type mappings"
    )
    notes: str = Field(
        default="",
        description="Any notes or assumptions the LLM made during schema inference",
    )
