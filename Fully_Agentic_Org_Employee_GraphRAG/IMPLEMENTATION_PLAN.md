# Fully Agentic GraphRAG — Implementation Plan

## Problem Statement

The current codebase is **100% hardcoded** to the AccenIndia Excel file. Every single module contains references to specific sheet names (`"Employees"`, `"Skills Catalog"`), column names (`"Employee_ID"`, `"Proficiency_Level"`), Neo4j labels (`:Employee`, `:Skill`), and relationship types (`:HAS_SKILL`, `:REPORTS_TO`). This means if someone uploads a different organization's data with different sheet structures, the system breaks completely.

**Goal**: Transform this into a **fully agentic system** where you can drop in *any* CSV/Excel file and the system will:
1. Automatically analyze the data structure
2. Use an LLM to infer the optimal graph schema (nodes, relationships, properties)
3. Dynamically generate and execute Cypher ingestion queries
4. Dynamically introspect the live Neo4j schema for the RAG chatbot

---

## Hardcoded Elements Audit

| File | Lines | What's Hardcoded |
|---|---|---|
| `ingest_graph.py` | 778 | Every function maps specific columns to specific Neo4j labels/properties. 10 node types, 15 relationship types, all handwritten. |
| `schema.py` | 155 | Two massive hardcoded strings describing the AccenIndia graph schema for LLM context |
| `cypher_templates.py` | 142 | 11 few-shot examples using AccenIndia-specific entity names ("Rahul Kapoor", "Python", "Data & AI") |
| `prompts.py` | 85 | Prompts embed the hardcoded schema + hardcoded skill name lists + hardcoded rules like "filter for employment_status = Active" |
| `data_loader.py` | 60 | Hardcoded skip list `{"Org Summary"}`, only handles Excel |
| `config.py` | 41 | Hardcoded default path to `accenIndia_org_model.xlsx` |

**Every file in the pipeline must change.**

---

## New Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       User uploads CSV/Excel                      │
└──────────────────────────┬───────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 1: Schema Discovery Agent (LLM-powered)                   │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────┐  │
│  │ Data Profiler│───▶│ LLM Schema  │───▶│ Graph Mapping JSON  │  │
│  │ (metadata)   │    │ Inference    │    │ (nodes, rels, keys) │  │
│  └─────────────┘    └──────────────┘    └─────────────────────┘  │
└──────────────────────────┬───────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 2: Dynamic Ingestion Engine                                │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────────────┐  │
│  │ Read Mapping │───▶│ Generate     │───▶│ Execute Cypher     │  │
│  │ JSON         │    │ Cypher       │    │ Batches on Neo4j   │  │
│  └──────────────┘    └──────────────┘    └────────────────────┘  │
└──────────────────────────┬───────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 3: Dynamic GraphRAG (runtime schema introspection)         │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │ Neo4j Schema   │─▶│ Dynamic      │─▶│ LangGraph Agent    │   │
│  │ Introspection  │  │ Prompt Build │  │ (same 4-node flow) │   │
│  └────────────────┘  └──────────────┘  └────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Detailed Design

### 1. Data Profiler (`src/schema_discovery/profiler.py`)

Reads any CSV/Excel and extracts metadata for LLM consumption.

**Input**: File path (xlsx, csv, or folder of csvs)
**Output**: A structured metadata dict per sheet/table:

```json
{
  "tables": [
    {
      "name": "Employees",
      "row_count": 151,
      "columns": [
        {"name": "Employee_ID", "dtype": "string", "unique_count": 151, "nulls": 0, "sample_values": ["EMP0001", "EMP0002"]},
        {"name": "Department_ID", "dtype": "string", "unique_count": 10, "nulls": 0, "sample_values": ["DEPT001", "DEPT002"]},
        {"name": "Manager_ID", "dtype": "string", "unique_count": 30, "nulls": 1, "sample_values": ["EMP0001", "EMP0002"]}
      ]
    }
  ]
}
```

Key heuristics extracted:
- **Cardinality** (unique count vs row count) — helps identify IDs vs attributes
- **Foreign key candidates** — columns whose values are a subset of another table's ID column
- **Data types** — string, numeric, datetime, boolean
- **Null ratios** — helps decide optional vs required properties
- **Sample values** — gives LLM context for semantic understanding

### 2. Schema Inference Agent (`src/schema_discovery/schema_agent.py`)

Sends the profiler metadata to the LLM with a carefully crafted prompt asking it to produce a **Graph Mapping Model** — a structured JSON document.

**Pydantic Output Schema (enforced via structured output)**:

```python
class NodeMapping(BaseModel):
    label: str                          # Neo4j label, e.g., "Employee"
    source_table: str                   # Which sheet/CSV to pull from
    primary_key_column: str             # Column to use as unique ID
    primary_key_property: str           # Neo4j property name for the key
    properties: list[PropertyMapping]   # Column → property mappings

class PropertyMapping(BaseModel):
    column_name: str                    # Source column
    property_name: str                  # Neo4j property name (snake_case)
    neo4j_type: str                     # "STRING" | "INTEGER" | "FLOAT" | "DATE" | "BOOLEAN"

class RelationshipMapping(BaseModel):
    type: str                           # Relationship type, e.g., "WORKS_IN"
    source_table: str                   # Table containing FK or junction data
    from_node_label: str                # Source node label
    from_key_column: str                # FK column in source table → from_node
    to_node_label: str                  # Target node label
    to_key_column: str                  # FK column in source table → to_node
    properties: list[PropertyMapping]   # Relationship properties (if junction table)

class GraphMappingModel(BaseModel):
    nodes: list[NodeMapping]
    relationships: list[RelationshipMapping]
    constraints: list[str]              # Cypher constraint statements
```

**Why Pydantic structured output?** This guarantees the LLM returns valid, parseable JSON every time. No regex parsing or "hope for the best" — we enforce the schema at the API level.

### 3. Dynamic Ingestion Engine (`src/ingestion/dynamic_ingest.py`)

Reads the `GraphMappingModel` and dynamically executes ingestion.

**For each NodeMapping:**
```python
def _build_node_cypher(mapping: NodeMapping) -> str:
    props = ", ".join(f"n.{p.property_name} = row.{p.property_name}" for p in mapping.properties)
    return f"""
    UNWIND $rows AS row
    MERGE (n:{mapping.label} {{{mapping.primary_key_property}: row.{mapping.primary_key_property}}})
    SET {props}
    """
```

**For each RelationshipMapping:**
```python
def _build_rel_cypher(mapping: RelationshipMapping) -> str:
    props = ""
    if mapping.properties:
        prop_sets = ", ".join(f"r.{p.property_name} = row.{p.property_name}" for p in mapping.properties)
        props = f"SET {prop_sets}"
    return f"""
    UNWIND $rows AS row
    MATCH (a:{mapping.from_node_label} {{{...}}})
    MATCH (b:{mapping.to_node_label} {{{...}}})
    MERGE (a)-[r:{mapping.type}]->(b)
    {props}
    """
```

The engine reads DataFrames, maps columns to properties using the mapping, and batch-executes the generated Cypher.

### 4. Dynamic Schema Introspection (`src/graph_rag/dynamic_schema.py`)

**Replaces** the hardcoded `schema.py`. At runtime, queries Neo4j for the live schema:

```python
def get_live_schema(db: Neo4jManager) -> str:
    """Query Neo4j to build schema text dynamically."""
    
    # Get node labels and their properties
    node_info = db.run_query("""
        CALL db.schema.nodeTypeProperties()
        YIELD nodeType, propertyName, propertyTypes
        RETURN nodeType, collect({prop: propertyName, types: propertyTypes}) AS properties
    """)
    
    # Get relationship types and their properties
    rel_info = db.run_query("""
        CALL db.schema.relTypeProperties()
        YIELD relType, propertyName, propertyTypes
        RETURN relType, collect({prop: propertyName, types: propertyTypes}) AS properties
    """)
    
    # Get actual relationship patterns (which nodes connect to which)
    patterns = db.run_query("CALL db.schema.visualization()")
    
    # Build formatted schema text
    return _format_schema(node_info, rel_info, patterns)
```

This means the chatbot automatically adapts to **whatever** graph is currently in Neo4j.

### 5. Dynamic Few-Shot Generator (`src/graph_rag/dynamic_examples.py`)

**Replaces** the hardcoded `cypher_templates.py`. Generates a small number of representative Cypher examples by:

1. Querying the live schema
2. For each relationship type, generating 1-2 template queries
3. Sampling actual node property values from the graph for realistic examples

```python
def generate_few_shots(db: Neo4jManager, schema_text: str, llm) -> str:
    """Ask LLM to generate few-shot Cypher examples based on the live schema."""
    # Sample some actual data from the graph
    samples = _sample_graph_data(db)
    
    prompt = f"""Given this Neo4j graph schema:
    {schema_text}
    
    And these sample data values:
    {samples}
    
    Generate 5-8 diverse example Cypher queries covering:
    - Simple node lookups
    - Multi-hop relationship traversals
    - Aggregation queries
    - Filtering with WHERE clauses
    
    Return as JSON array of {{question, cypher}} objects."""
    
    return llm.invoke(prompt)
```

### 6. Updated Prompts (`src/graph_rag/prompts.py`)

All prompts become **template strings** with `{schema}`, `{few_shots}`, `{sample_values}` placeholders filled at runtime — zero hardcoded domain knowledge.

### 7. Updated Agent (`src/graph_rag/agent.py`)

The agent's `__init__` now:
1. Calls `get_live_schema()` to fetch current schema
2. Calls `generate_few_shots()` to build examples
3. Builds prompts dynamically from templates + live schema

### 8. Updated Streamlit UI (`app.py`)

Adds a **file upload** widget so users can:
1. Upload a new Excel/CSV
2. Click "Analyze & Ingest" to trigger the Schema Discovery → Ingestion pipeline
3. The chat automatically adapts to the new graph

---

## File Change Summary

### Files to DELETE (replaced entirely)
- `src/ingestion/ingest_graph.py` — replaced by `dynamic_ingest.py`
- `src/graph_rag/schema.py` — replaced by `dynamic_schema.py`
- `src/graph_rag/cypher_templates.py` — replaced by `dynamic_examples.py`

### Files to CREATE (new)
- `src/schema_discovery/__init__.py`
- `src/schema_discovery/profiler.py` — data profiling engine
- `src/schema_discovery/schema_agent.py` — LLM-powered schema inference
- `src/schema_discovery/models.py` — Pydantic models for GraphMappingModel
- `src/ingestion/dynamic_ingest.py` — generic ingestion from mapping
- `src/graph_rag/dynamic_schema.py` — runtime Neo4j schema introspection
- `src/graph_rag/dynamic_examples.py` — runtime few-shot generation

### Files to MODIFY
- `src/config.py` — remove hardcoded Excel path, add `MAPPING_DIR` for saved mappings
- `src/data_loader.py` — support CSV folders + remove hardcoded skip list
- `src/graph_rag/prompts.py` — make all prompts template-based (no embedded schema)
- `src/graph_rag/agent.py` — init with dynamic schema, not hardcoded imports
- `app.py` — add file upload + "Analyze & Ingest" flow
- `ingest.py` — rewrite CLI to use dynamic pipeline
- `requirements.txt` — no changes needed (already has pydantic, langchain)

---

## Implementation Order

### Step 1: Pydantic Models (`models.py`)
Define `GraphMappingModel`, `NodeMapping`, `RelationshipMapping`, `PropertyMapping`.

### Step 2: Data Profiler (`profiler.py`)
Build the metadata extraction engine for any CSV/Excel.

### Step 3: Schema Discovery Agent (`schema_agent.py`)
LLM-powered schema inference with structured Pydantic output.

### Step 4: Dynamic Ingestion Engine (`dynamic_ingest.py`)
Generic Cypher generator + executor from GraphMappingModel.

### Step 5: Dynamic Schema Introspection (`dynamic_schema.py`)
Query Neo4j for live schema at runtime.

### Step 6: Dynamic Few-Shot Generator (`dynamic_examples.py`)
LLM-generated Cypher examples from live schema.

### Step 7: Updated Prompts (`prompts.py`)
Template-based prompts with runtime injection.

### Step 8: Updated Agent (`agent.py`)
Wire everything together with dynamic schema.

### Step 9: Updated CLI (`ingest.py`)
New pipeline: load → profile → infer schema → ingest.

### Step 10: Updated Streamlit UI (`app.py`)
File upload widget + schema discovery UI.

### Step 11: Updated Config & Data Loader
Remove all hardcoded paths and skip lists.

---

## Verification Plan

### Test with AccenIndia data (regression)
- Run the new pipeline on the original `accenIndia_org_model.xlsx`
- Verify node/relationship counts match the old hardcoded approach
- Verify the chatbot answers the same questions correctly

### Test with a completely different dataset
- Create or find a different organizational dataset with different sheet names/columns
- Verify the system automatically discovers the schema and ingests correctly

### Edge Cases
- CSV files (single table, no sheets)
- Missing data / high null ratios
- Tables with no clear foreign key relationships
- Very wide tables (50+ columns)
