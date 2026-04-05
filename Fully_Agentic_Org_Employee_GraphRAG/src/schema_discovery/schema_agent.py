"""
Schema Discovery Agent — uses an LLM to infer a Neo4j graph schema
from tabular data metadata.

Takes the profiler output and returns a validated GraphMappingModel.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from src.llm_factory import get_llm
from src.schema_discovery.models import GraphMappingModel
from src.schema_discovery.profiler import profile_to_text
from src.utils.logger import log


# ───────────────────────────────────────────────────────────────────────
# Prompt
# ───────────────────────────────────────────────────────────────────────

SCHEMA_INFERENCE_PROMPT = """You are an expert graph database architect. Your task is to analyze tabular data metadata and design an optimal Neo4j property graph schema.

Given the following data profile (table names, columns, types, cardinality, sample values, and detected foreign keys), produce a complete graph mapping.

{profile_text}

INSTRUCTIONS:
1. IDENTIFY NODE TYPES:
   - Tables with many unique rows and a clear primary key column (usually the first column ending with "_ID" or "ID") should become Node types.
   - Each node type must have exactly ONE primary key property.
   - Use PascalCase for node labels (e.g., "Employee", "Skill", "Project").
   - Map ALL useful columns from the source table as node properties.
   - Use snake_case for property names.
   - Determine the correct neo4j_type for each property: STRING, INTEGER, FLOAT, DATE, BOOLEAN.

2. IDENTIFY RELATIONSHIP TYPES:
   - Foreign key columns indicate relationships between nodes.
   - Junction tables (tables with two FK columns and additional columns) become relationships WITH properties.
   - Self-referencing FKs (e.g., Manager_ID in an Employee table) become self-relationships.
   - Use UPPER_SNAKE_CASE for relationship types (e.g., "HAS_SKILL", "WORKS_IN").
   - Include the correct from_key_column and to_key_column values.
   - Any non-FK columns in junction tables should become relationship properties.

3. HANDLE SPECIAL CASES:
   - If a column has very few unique values but appears in many rows, it might be worth extracting as its own node (e.g., a "Status" column with 3 values might NOT need its own node, but a "Department" column with 10 values referenced by 100+ employees SHOULD be a node if there's a separate department table).
   - Columns that look like they reference another table but have no dedicated table for them (e.g., "University" in an employee table) can become nodes with just a name property — create them from the column values directly. For these, set source_table to the table containing the column, and use the column itself as both from_key_column and to_key_column.
   - Date columns should use neo4j_type "DATE".
   - Boolean-like columns ("Yes"/"No", "True"/"False") should use neo4j_type "STRING" (store as-is).
   
4. SKIP non-data tables (dashboards, summaries with merged cells, tables with no clear structure).

5. For relationships where to_key_column references a node's primary key but the column name in the source table is different, specify the ACTUAL column name in the source table as to_key_column.

Return a valid JSON object conforming to the GraphMappingModel schema.
"""


# ───────────────────────────────────────────────────────────────────────
# Agent
# ───────────────────────────────────────────────────────────────────────

def infer_graph_schema(
    profile: Dict[str, Any],
    llm_provider: str | None = None,
    save_path: str | None = None,
) -> GraphMappingModel:
    """
    Use an LLM to infer a graph schema from data profile metadata.

    Args:
        profile:      Output from profiler.profile_data()
        llm_provider: Override LLM provider
        save_path:    If set, save the JSON mapping to this path

    Returns:
        Validated GraphMappingModel
    """
    log.info("[bold cyan]Schema Agent[/] Inferring graph schema from data profile …")

    llm = get_llm(provider=llm_provider)
    profile_text = profile_to_text(profile)

    prompt = SCHEMA_INFERENCE_PROMPT.format(profile_text=profile_text)

    # Use structured output if the LLM supports it
    try:
        structured_llm = llm.with_structured_output(GraphMappingModel)
        mapping: GraphMappingModel = structured_llm.invoke([
            SystemMessage(content="You are an expert graph database architect. Return a valid GraphMappingModel JSON."),
            HumanMessage(content=prompt),
        ])
    except (NotImplementedError, AttributeError, Exception) as e:
        log.info(f"[bold yellow]Schema Agent[/] Structured output not available ({type(e).__name__}), falling back to JSON parsing …")
        mapping = _fallback_json_parse(llm, prompt)

    log.info(
        f"[bold cyan]Schema Agent[/] ✅ Inferred schema: "
        f"{len(mapping.nodes)} node types, {len(mapping.relationships)} relationship types"
    )

    # Log the schema details
    for node in mapping.nodes:
        log.info(f"  📦 :{node.label} ({len(node.properties)} properties) ← {node.source_table}")
    for rel in mapping.relationships:
        log.info(f"  🔗 (:{rel.from_node_label})-[:{rel.type}]->(:{rel.to_node_label})")

    # Save mapping
    if save_path:
        _save_mapping(mapping, save_path)

    return mapping


def _fallback_json_parse(llm, prompt: str) -> GraphMappingModel:
    """Fallback: ask LLM for raw JSON and parse manually."""
    from langchain_core.messages import HumanMessage, SystemMessage

    response = llm.invoke([
        SystemMessage(
            content=(
                "You are an expert graph database architect. "
                "Return ONLY a valid JSON object (no markdown, no code fences) "
                "conforming to the GraphMappingModel schema with keys: "
                "nodes (list), relationships (list), notes (string)."
            )
        ),
        HumanMessage(content=prompt),
    ])

    raw = response.content.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        # Remove first and last lines (``` markers)
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        import re
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            raise ValueError(f"Could not parse LLM response as JSON:\n{raw[:500]}")

    return GraphMappingModel(**data)


def _save_mapping(mapping: GraphMappingModel, path: str) -> None:
    """Save the graph mapping to a JSON file."""
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(mapping.model_dump_json(indent=2))
    log.info(f"[bold cyan]Schema Agent[/] 💾 Mapping saved to {path}")


def load_mapping(path: str) -> GraphMappingModel:
    """Load a previously saved graph mapping from JSON."""
    from pathlib import Path
    raw = Path(path).read_text()
    return GraphMappingModel.model_validate_json(raw)
