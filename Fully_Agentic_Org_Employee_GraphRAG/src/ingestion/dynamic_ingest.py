"""
Dynamic Ingestion Engine — reads a GraphMappingModel and ingests
any tabular data into Neo4j without hardcoded schema knowledge.

Dynamically generates Cypher MERGE statements from the mapping.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from src.neo4j_manager import Neo4jManager
from src.schema_discovery.models import (
    GraphMappingModel,
    NodeMapping,
    PropertyMapping,
    RelationshipMapping,
)
from src.utils.logger import log


# ───────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────

def _safe(val: Any) -> Any:
    """Convert pandas NaN / NaT to None for Neo4j."""
    if pd.isna(val):
        return None
    if isinstance(val, pd.Timestamp):
        return val.isoformat()
    return val


def _neo4j_cast(prop: PropertyMapping) -> str:
    """Return a Cypher cast expression for a property."""
    p = f"row.{prop.property_name}"
    if prop.neo4j_type == "INTEGER":
        return f"toInteger({p})"
    elif prop.neo4j_type == "FLOAT":
        return f"toFloat({p})"
    elif prop.neo4j_type == "BOOLEAN":
        return f"toBoolean({p})"
    return p  # STRING and DATE stay as-is


# ───────────────────────────────────────────────────────────────────────
# Constraint Generation
# ───────────────────────────────────────────────────────────────────────

def _generate_constraints(mapping: GraphMappingModel) -> List[str]:
    """Generate uniqueness constraint Cypher for every node type."""
    constraints = []
    for node in mapping.nodes:
        label = node.label
        pk = node.primary_key_property
        constraints.append(
            f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) "
            f"REQUIRE n.{pk} IS UNIQUE"
        )
    return constraints


def create_constraints(db: Neo4jManager, mapping: GraphMappingModel) -> None:
    """Execute uniqueness constraints on Neo4j."""
    constraints = _generate_constraints(mapping)
    log.info(f"[bold yellow]Creating {len(constraints)} constraints …[/]")
    for c in constraints:
        try:
            db.run_write(c)
        except Exception as e:
            log.warning(f"  ⚠️ Constraint skipped: {e}")
    log.info(f"  ✅ Constraints created")


# ───────────────────────────────────────────────────────────────────────
# Node Ingestion
# ───────────────────────────────────────────────────────────────────────

def _build_node_cypher(node: NodeMapping) -> str:
    """Dynamically build a Cypher MERGE + SET for a node type."""
    pk_prop = node.primary_key_property

    # Find the PK property mapping to determine its type
    pk_cast = f"row.{pk_prop}"
    for p in node.properties:
        if p.property_name == pk_prop:
            pk_cast = _neo4j_cast(p)
            break

    # Build SET clauses for all non-PK properties
    set_parts = []
    for p in node.properties:
        if p.property_name == pk_prop:
            continue
        set_parts.append(f"n.{p.property_name} = {_neo4j_cast(p)}")

    set_clause = ""
    if set_parts:
        set_clause = "SET " + ",\n        ".join(set_parts)

    return f"""
    UNWIND $rows AS row
    MERGE (n:{node.label} {{{pk_prop}: {pk_cast}}})
    {set_clause}
    """


def _prepare_node_rows(
    node: NodeMapping,
    df: pd.DataFrame,
) -> List[Dict[str, Any]]:
    """Convert DataFrame rows to dicts using the node's property mappings."""
    rows = []
    for _, r in df.iterrows():
        row_dict = {}
        for p in node.properties:
            if p.column_name in df.columns:
                row_dict[p.property_name] = _safe(r[p.column_name])
            else:
                row_dict[p.property_name] = None
        rows.append(row_dict)
    return rows


def ingest_nodes(
    db: Neo4jManager,
    node: NodeMapping,
    df: pd.DataFrame,
) -> int:
    """Ingest a single node type from a DataFrame."""
    log.info(f"[bold magenta]Ingesting :{node.label} nodes from '{node.source_table}' …[/]")

    cypher = _build_node_cypher(node)
    rows = _prepare_node_rows(node, df)

    if not rows:
        log.info(f"  ⚠️ No rows to ingest for :{node.label}")
        return 0

    count = db.run_write_batch(cypher, rows)
    log.info(f"  ✅ {count} :{node.label} nodes")
    return count


# ───────────────────────────────────────────────────────────────────────
# Relationship Ingestion
# ───────────────────────────────────────────────────────────────────────

def _find_node_pk(mapping: GraphMappingModel, label: str) -> str:
    """Find the primary key property name for a given node label."""
    for node in mapping.nodes:
        if node.label == label:
            return node.primary_key_property
    raise ValueError(f"No node mapping found for label '{label}'")


def _build_rel_cypher(
    rel: RelationshipMapping,
    mapping: GraphMappingModel,
) -> str:
    """Dynamically build a Cypher MATCH + MERGE for a relationship."""
    from_pk = _find_node_pk(mapping, rel.from_node_label)
    to_pk = _find_node_pk(mapping, rel.to_node_label)

    # Build SET for relationship properties
    set_parts = []
    for p in rel.properties:
        set_parts.append(f"r.{p.property_name} = {_neo4j_cast(p)}")

    set_clause = ""
    if set_parts:
        set_clause = "SET " + ",\n        ".join(set_parts)

    return f"""
    UNWIND $rows AS row
    MATCH (a:{rel.from_node_label} {{{from_pk}: row.__from_key}})
    MATCH (b:{rel.to_node_label} {{{to_pk}: row.__to_key}})
    MERGE (a)-[r:{rel.type}]->(b)
    {set_clause}
    """


def _prepare_rel_rows(
    rel: RelationshipMapping,
    df: pd.DataFrame,
) -> List[Dict[str, Any]]:
    """Convert DataFrame rows to dicts for relationship ingestion."""
    rows = []
    for _, r in df.iterrows():
        # Get the FK values
        from_val = _safe(r.get(rel.from_key_column))
        to_val = _safe(r.get(rel.to_key_column))

        if from_val is None or to_val is None:
            continue

        row_dict = {
            "__from_key": from_val,
            "__to_key": to_val,
        }

        # Add relationship properties
        for p in rel.properties:
            if p.column_name in df.columns:
                row_dict[p.property_name] = _safe(r[p.column_name])
            else:
                row_dict[p.property_name] = None

        rows.append(row_dict)
    return rows


def ingest_relationships(
    db: Neo4jManager,
    rel: RelationshipMapping,
    df: pd.DataFrame,
    mapping: GraphMappingModel,
) -> int:
    """Ingest a single relationship type from a DataFrame."""
    log.info(
        f"[bold magenta]Ingesting [:{rel.type}] "
        f"(:{rel.from_node_label})→(:{rel.to_node_label}) "
        f"from '{rel.source_table}' …[/]"
    )

    cypher = _build_rel_cypher(rel, mapping)
    rows = _prepare_rel_rows(rel, df)

    if not rows:
        log.info(f"  ⚠️ No rows to ingest for [:{rel.type}]")
        return 0

    count = db.run_write_batch(cypher, rows)
    log.info(f"  ✅ {count} [:{rel.type}] relationships")
    return count


# ───────────────────────────────────────────────────────────────────────
# Master Orchestrator
# ───────────────────────────────────────────────────────────────────────

def run_dynamic_ingestion(
    db: Neo4jManager,
    tables: Dict[str, pd.DataFrame],
    mapping: GraphMappingModel,
    clear_first: bool = True,
) -> Dict[str, int]:
    """
    Run the full dynamic ingestion pipeline.

    Args:
        db:          Connected Neo4jManager instance.
        tables:      Dict of table_name → DataFrame.
        mapping:     GraphMappingModel from schema discovery.
        clear_first: If True, wipe the database before ingesting.

    Returns:
        Final node/relationship counts.
    """
    log.info("[bold green]═══ Starting Dynamic Ingestion Pipeline ═══[/]")

    if clear_first:
        db.clear_database()

    # 1. Create constraints
    create_constraints(db, mapping)

    # 2. Ingest all node types
    log.info("\n[bold green]── Phase 1: Nodes ──[/]")
    for node in mapping.nodes:
        table_name = node.source_table
        if table_name not in tables:
            log.warning(f"  ⚠️ Table '{table_name}' not found in data. Skipping :{node.label}")
            continue
        ingest_nodes(db, node, tables[table_name])

    # 3. Ingest all relationships
    log.info("\n[bold green]── Phase 2: Relationships ──[/]")
    for rel in mapping.relationships:
        table_name = rel.source_table
        if table_name not in tables:
            log.warning(f"  ⚠️ Table '{table_name}' not found for [:{rel.type}]. Skipping.")
            continue
        ingest_relationships(db, rel, tables[table_name], mapping)

    # 4. Final stats
    counts = db.get_counts()
    log.info(
        f"\n[bold green]═══ Dynamic Ingestion Complete ═══[/] "
        f"Nodes: {counts['nodes']}  |  Relationships: {counts['relationships']}"
    )
    return counts
