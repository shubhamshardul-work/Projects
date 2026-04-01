# Contract Intelligence Knowledge Graph — Implementation Plan v2

## Philosophy

This plan keeps things **simple in the initial phase** — no embeddings, no vector stores, no hybrid search, no governance layer yet.

The entire pipeline is orchestrated as a **LangGraph state machine**: each stage is a node in the graph, with conditional edges for routing. The mapper supports **dual mode** (rule-based OR LLM-based), selectable from the UI. Items flagged during validation enter a **human-in-the-loop** review step powered by LangGraph's `interrupt` mechanism.

Pipeline: **Document → Diffbot extracts → Bridge/Mapper (rule or LLM) → Validate → [Human Review] → Neo4j ingest → Graph RAG answers**

---

## High-Level Architecture

```
                              ┌──────────────────────────────────┐
                              │         Streamlit UI              │
                              │  Upload · Config · Review · Q&A  │
                              └──────────┬───────────────────────┘
                                         │ (FastAPI)
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        LangGraph Pipeline (State Machine)                    │
│                                                                              │
│  ┌──────────┐   ┌──────────┐   ┌────────────┐   ┌──────────────────────┐   │
│  │  Load &   │──▶│ Diffbot  │──▶│  Mapper    │──▶│  Validate            │   │
│  │ Preprocess│   │ Extract  │   │ (Rule/LLM) │   │  + Confidence Score  │   │
│  └──────────┘   └──────────┘   └────────────┘   └──────────┬───────────┘   │
│                                                              │               │
│                                              ┌───────────────┴────────┐      │
│                                              ▼                        ▼      │
│                                     ┌────────────────┐   ┌────────────────┐  │
│                                     │ Human Review   │   │   Auto-pass    │  │
│                                     │ (interrupt)    │   │                │  │
│                                     └───────┬────────┘   └───────┬────────┘  │
│                                             └────────┬───────────┘           │
│                                                      ▼                       │
│                                             ┌────────────────┐               │
│                                             │  Neo4j Ingest  │               │
│                                             │  (LangChain)   │               │
│                                             └────────────────┘               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
                              ┌──────────────────────┐
                              │  Graph RAG            │
                              │  (NL → Cypher → Answer)│
                              └──────────────────────┘
```

**Five pillars:**

| #   | Pillar         | Engine                                                               | LLM needed?   |
| --- | -------------- | -------------------------------------------------------------------- | ------------- |
| 1   | Orchestration  | LangGraph state machine                                              | No            |
| 2   | Extraction     | Diffbot NLP API                                                      | No            |
| 3   | Mapping (dual) | Python rules + fuzzy matching **OR** LLM-based structured extraction | Configurable  |
| 4   | Ingestion      | LangChain `Neo4jGraph` + `add_graph_documents`                       | No            |
| 5   | Query          | Graph RAG (NL → Cypher → answer)                                     | Yes (minimal) |

---

## Technology Stack

| Layer             | Technology                                    | Why                                                                                                                   |
| ----------------- | --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **Orchestration** | **LangGraph**                                 | State machine for the entire pipeline; supports conditional routing, human-in-the-loop via `interrupt`, checkpointing |
| Extraction        | Diffbot Natural Language API                  | Structured entity/relationship extraction, no training, no prompting                                                  |
| Text extraction   | `pdfplumber`, `python-docx`                   | Extract text from PDFs and DOCX before Diffbot                                                                        |
| Mapping (rule)    | Pure Python + `rapidfuzz`                     | Deterministic, fast, free, debuggable                                                                                 |
| Mapping (LLM)     | LangChain `ChatOpenAI` with structured output | Uses ontology as schema, extracts and maps entities via LLM when rule-based is insufficient                           |
| Validation        | `pydantic` v2                                 | Schema enforcement before Neo4j write                                                                                 |
| Graph database    | Neo4j Community / Aura                        | Knowledge graph storage and Cypher queries                                                                            |
| Neo4j ingestion   | LangChain `Neo4jGraph` + custom Cypher        | `Neo4jGraph.query()` for Cypher execution, MERGE-based upserts                                                        |
| Graph RAG         | LangChain `GraphCypherQAChain`                | NL → Cypher → answer, minimal LLM use                                                                                 |
| LLM               | OpenAI GPT-4o-mini                            | Used for: (a) LLM mapper mode, (b) Graph RAG query. Not used in rule-based mode.                                      |
| API layer         | FastAPI                                       | Backend endpoints for UI                                                                                              |
| **UI**            | **Streamlit**                                 | Upload documents, toggle mapper mode, review flagged items, ask questions                                             |
| Config            | `python-dotenv`                               | Environment management                                                                                                |

---

## Project Structure

```
Project_02/
├── doc/
│   ├── FLOW.md
│   └── IMPLEMENTATION_PLAN.md
├── app/
│   ├── __init__.py
│   ├── config.py                       # Env vars, API keys, paths
│   ├── models/
│   │   ├── __init__.py
│   │   ├── ontology.py                 # Canonical node/relationship type definitions
│   │   └── schemas.py                  # Pydantic models for graph data + pipeline state
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── document_loader.py          # PDF/DOCX text extraction
│   │   ├── document_registry.py        # Document inventory tracking (JSON file)
│   │   └── preprocessor.py             # Text cleaning, section splitting
│   ├── extraction/
│   │   ├── __init__.py
│   │   └── diffbot_client.py           # Diffbot NLP API wrapper + caching
│   ├── mapper/
│   │   ├── __init__.py
│   │   ├── rule_mapper.py              # Rule-based: regex + section context + fuzzy matching
│   │   ├── llm_mapper.py              # LLM-based: structured output extraction via LangChain
│   │   ├── entity_resolver.py          # Fuzzy dedup with rapidfuzz
│   │   └── relationship_builder.py     # Map/infer relationships to canonical types
│   ├── graph_db/
│   │   ├── __init__.py
│   │   ├── neo4j_client.py             # LangChain Neo4jGraph wrapper
│   │   ├── loader.py                   # Canonical JSON → Cypher MERGE via LangChain
│   │   └── queries.py                  # Index creation + common Cypher templates
│   ├── rag/
│   │   ├── __init__.py
│   │   └── graph_rag.py                # GraphCypherQAChain with few-shot examples
│   ├── pipeline/
│   │   ├── __init__.py
│   │   └── graph_workflow.py           # LangGraph state machine (the whole pipeline)
│   └── api/
│       ├── __init__.py
│       └── endpoints.py                # FastAPI routes
├── ui/
│   └── streamlit_app.py               # Streamlit frontend
├── tests/
│   ├── __init__.py
│   ├── test_document_loader.py
│   ├── test_diffbot_client.py
│   ├── test_mapper.py
│   ├── test_neo4j_loader.py
│   └── test_graph_rag.py
├── data/
│   ├── raw/                            # Drop zone for source PDFs/DOCX
│   ├── extracted/                      # Diffbot JSON responses cached
│   ├── mapped/                         # Canonical JSON after mapping
│   └── logs/                           # Pipeline run logs
├── scripts/
│   ├── seed_sample.py
│   └── reset_graph.py
├── requirements.txt
├── .env.example
└── main.py                             # FastAPI app entry point
```

---

# PHASE 1 — Canonical Ontology & Pydantic Models

## Step 1.1: Define the canonical ontology in code

File: `app/models/ontology.py`

This is the single source of truth. Every Diffbot entity and relationship will be filtered and mapped against this ontology.

### Node types

```python
class NodeType(str, Enum):
    CLIENT = "Client"
    ACCOUNT = "Account"
    ENGAGEMENT = "Engagement"
    PROJECT = "Project"
    CONTRACT = "Contract"
    MSA = "MSA"
    SOW = "SOW"
    AMENDMENT = "Amendment"
    CHANGE_REQUEST = "ChangeRequest"
    CLAUSE = "Clause"
    SECTION = "Section"
    DELIVERABLE = "Deliverable"
    MILESTONE = "Milestone"
    SLA = "SLA"
    KPI = "KPI"
    PRICING_MODEL = "PricingModel"
    RESOURCE_ROLE = "ResourceRole"
    LEGAL_ENTITY = "LegalEntity"
    LOCATION = "Location"
    VERSION = "Version"
```

### Relationship types

```python
class RelationshipType(str, Enum):
    HAS_ACCOUNT = "HAS_ACCOUNT"
    HAS_ENGAGEMENT = "HAS_ENGAGEMENT"
    HAS_PROJECT = "HAS_PROJECT"
    GOVERNED_BY = "GOVERNED_BY"
    HAS_SOW = "HAS_SOW"
    HAS_AMENDMENT = "HAS_AMENDMENT"
    HAS_CLAUSE = "HAS_CLAUSE"
    HAS_DELIVERABLE = "HAS_DELIVERABLE"
    HAS_MILESTONE = "HAS_MILESTONE"
    TRACKED_BY = "TRACKED_BY"
    MODIFIED_BY = "MODIFIED_BY"
    SUPERSEDED_BY = "SUPERSEDED_BY"
    REFERS_TO = "REFERS_TO"
    USES_PRICING_MODEL = "USES_PRICING_MODEL"
    DELIVERED_BY = "DELIVERED_BY"
    HAS_SECTION = "HAS_SECTION"
    REVISED_BY = "REVISED_BY"
    HAS_VERSION = "HAS_VERSION"
    HAS_SLA = "HAS_SLA"
    HAS_KPI = "HAS_KPI"
    BELONGS_TO = "BELONGS_TO"
```

### Property schemas per node type

`NODE_PROPERTY_SCHEMA` dict maps each `NodeType` to its required and optional properties. Used for validation before Neo4j write and for guiding the LLM mapper's structured output schema.

---

## Step 1.2: Pydantic models + LangGraph pipeline state

File: `app/models/schemas.py`

### Graph data models

- `GraphNode` — type, id, properties
- `GraphRelationship` — from_id, from_type, to_id, to_type, relationship type, properties
- `DocumentExtractionResult` — the canonical intermediate JSON for one document (nodes, rels, unmapped items, warnings)
- `DocumentRecord` — document metadata for the inventory

### LangGraph pipeline state

```python
class PipelineState(TypedDict):
    # Input
    file_path: str
    client_name: str
    project_name: str
    mapper_mode: str              # "rule" or "llm" — set from UI checkbox

    # Pipeline data (populated by each node)
    document_id: str
    raw_text: str
    cleaned_text: str
    sections: list
    diffbot_results: list
    mapped_result: dict           # DocumentExtractionResult serialized
    needs_review: bool            # Set by validation node
    review_items: list            # Items needing human review
    human_decisions: list         # Populated after human review
    ingestion_summary: dict

    # Status
    status: str                   # "running" | "review" | "completed" | "failed"
    error: str
```

This state is passed through every node in the LangGraph pipeline. Each node reads what it needs and writes its outputs.

---

# PHASE 2 — Document Loading & Preprocessing

Same as before. Files: `app/ingest/document_loader.py`, `app/ingest/preprocessor.py`, `app/ingest/document_registry.py`.

### document_loader.py

- `extract_text_from_pdf(file_path)` — uses `pdfplumber`, returns page-by-page text + full text
- `extract_text_from_docx(file_path)` — uses `python-docx`, returns paragraphs + full text
- `load_document(file_path)` — routes based on file extension

### preprocessor.py

- `clean_text(text)` — collapse whitespace, strip noise
- `detect_sections(text)` — regex-based section heading detection for contracts (numbered sections, ARTICLE, SCHEDULE, EXHIBIT, etc.)
- `preprocess_document(raw)` — full pipeline: clean + section split

### document_registry.py

- JSON-file-based inventory tracker
- `register_document()`, `update_status()`, `get_pending_documents()`

---

# PHASE 3 — Diffbot Extraction

File: `app/extraction/diffbot_client.py`

### Core functions

- `_call_diffbot(text)` — POST to `https://nl.diffbot.com/v1/` with text, return JSON
- `extract_entities_and_relationships(text, document_id, cache_dir)` — call Diffbot, cache response, handle chunking for long texts
- `extract_by_section(sections, document_id)` — send each section independently, tag results with section metadata

### Design decisions

- Cache every response to `data/extracted/{id}.json` — saves API costs, creates audit trail
- Section-level extraction for better accuracy and traceability
- Max 50K chars per API call; auto-split if needed

---

# PHASE 4 — Bridge / Mapper (Dual Mode)

This is the most important custom code. Two implementations, same interface:

## Step 4.1: Document type classification (shared)

Both mapper modes use the same regex-based classifier:

```python
DOC_TYPE_PATTERNS = {
    "MSA": [r"master\s+service[s]?\s+agreement", r"\bMSA\b"],
    "SOW": [r"statement\s+of\s+work", r"\bSOW\b", r"scope\s+of\s+work"],
    "Amendment": [r"amendment\s+(no\.?|number|#)?\s*\d+"],
    "ChangeRequest": [r"change\s+(request|order|notice)"],
    "SLA": [r"service\s+level\s+agreement", r"\bSLA\b"],
    "PricingExhibit": [r"pricing\s+(exhibit|schedule|appendix)"],
}

def classify_document(text, file_name) -> str:
    # Scan first 2000 chars + filename, return best match or "Unknown"
```

---

## Step 4.2: Rule-Based Mapper

File: `app/mapper/rule_mapper.py`

### Entity mapping strategy

1. **Diffbot type + keyword heuristics**: `Organization` + legal suffix → `LegalEntity`, `Organization` + client keyword → `Client`
2. **Section context**: entity from "Deliverables" section → `Deliverable`
3. **Fallback**: unmatched entities go to `unmapped_entities` list

### Code structure

```python
ENTITY_MAPPING_RULES = [
    ("Organization", [r"client", r"customer", r"buyer"], NodeType.CLIENT),
    ("Organization", [r"inc\.", r"ltd", r"llc", r"gmbh", r"corp"], NodeType.LEGAL_ENTITY),
    ("Organization", [], NodeType.LEGAL_ENTITY),
    ("Location", [], NodeType.LOCATION),
    ("Person", [r"manager", r"lead", r"director"], NodeType.RESOURCE_ROLE),
]

SECTION_ENTITY_HINTS = {
    "deliverable": NodeType.DELIVERABLE,
    "milestone": NodeType.MILESTONE,
    "service level": NodeType.SLA,
    "pricing": NodeType.PRICING_MODEL,
    ...
}

def map_diffbot_entity_to_node(entity, section_heading, document_type, id_prefix) -> GraphNode | None
def map_document_rule_based(diffbot_results, document_id, file_name, source_file, text) -> DocumentExtractionResult
```

### Pros: deterministic, fast, free, debuggable

### Cons: can't handle novel entity patterns without new rules

---

## Step 4.3: LLM-Based Mapper

File: `app/mapper/llm_mapper.py`

Uses LangChain's structured output to map Diffbot entities to the canonical ontology.

### How it works

1. Take the Diffbot entities + section context for one section
2. Build a prompt that includes the canonical ontology (all node types and their properties)
3. Ask the LLM to return a structured JSON matching our `GraphNode` / `GraphRelationship` schemas
4. Use Pydantic to parse and validate the response

### Code structure

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

SYSTEM_PROMPT = """You are an entity mapping agent for a contract intelligence knowledge graph.

Given Diffbot extraction results from a contract document section, map each entity to the
correct canonical node type and extract its properties.

Canonical node types: {node_types}
Canonical relationship types: {relationship_types}
Property schemas: {property_schemas}

Rules:
- Only use canonical types from the list above
- If an entity does not fit any type, mark it as unmapped
- Extract all available properties that match the schema
- Assign a confidence score (0.0-1.0) to each mapping
- For relationships, use the canonical types and correct direction
"""

class LLMMapperOutput(BaseModel):
    nodes: list[GraphNode]
    relationships: list[GraphRelationship]
    unmapped: list[dict]
    confidence_scores: dict[str, float]  # node_id → confidence

def map_section_with_llm(entities, relationships, section_heading, document_type) -> LLMMapperOutput
def map_document_llm_based(diffbot_results, document_id, file_name, source_file, text) -> DocumentExtractionResult
```

### Confidence scoring

The LLM assigns a confidence score (0.0–1.0) to each entity mapping. Entities below 0.7 are flagged for human review. This directly feeds the human-in-the-loop step.

### Pros: handles novel patterns, more accurate for ambiguous entities

### Cons: slower, costs money, non-deterministic

---

## Step 4.4: Entity resolution (shared)

File: `app/mapper/entity_resolver.py`

Both mapper modes use the same deduplication:

```python
from rapidfuzz import fuzz, process

def deduplicate_nodes(nodes, threshold=85) -> list[GraphNode]:
    # Fuzzy match names within same type, merge properties
```

---

## Step 4.5: Relationship builder (shared)

File: `app/mapper/relationship_builder.py`

```python
STRUCTURAL_RELATIONSHIP_RULES = {
    (NodeType.CLIENT, NodeType.ACCOUNT): RelationshipType.HAS_ACCOUNT,
    (NodeType.SOW, NodeType.DELIVERABLE): RelationshipType.HAS_DELIVERABLE,
    ...
}

def map_diffbot_relationship(diffbot_rel, node_lookup) -> GraphRelationship | None
def infer_structural_relationships(nodes, document_type) -> list[GraphRelationship]
```

---

# PHASE 5 — Neo4j Ingestion (via LangChain)

## Step 5.1: Neo4j client using LangChain

File: `app/graph_db/neo4j_client.py`

Uses `langchain_community.graphs.Neo4jGraph` as the primary interface:

```python
from langchain_community.graphs import Neo4jGraph

class Neo4jClient:
    def __init__(self):
        self.graph = Neo4jGraph(
            url=NEO4J_URI,
            username=NEO4J_USER,
            password=NEO4J_PASSWORD,
        )

    def query(self, cypher: str, params: dict = None) -> list[dict]:
        return self.graph.query(cypher, params=params)

    def refresh_schema(self):
        self.graph.refresh_schema()

    @property
    def schema(self) -> str:
        return self.graph.schema
```

### Why LangChain Neo4jGraph

- Same object is reused by `GraphCypherQAChain` for RAG queries
- `.query()` method executes arbitrary Cypher (MERGE, CREATE, MATCH)
- `.schema` auto-fetches the current graph schema (used by RAG for Cypher generation)
- Single connection object used across ingestion and querying

## Step 5.2: Graph loader

File: `app/graph_db/loader.py`

Same MERGE-based approach but using the LangChain client:

```python
def load_extraction_result(client: Neo4jClient, result: DocumentExtractionResult) -> dict:
    # For each node: MERGE (n:Label {id: $id}) SET n.prop = $val
    # For each rel: MATCH (a), (b) MERGE (a)-[r:TYPE]->(b)
    # Returns summary with counts and errors
```

## Step 5.3: Indexes + common queries

File: `app/graph_db/queries.py`

- Auto-create indexes for every node type on `id`
- Common Cypher query templates (all SOWs for client, clauses by amendment, deliverables for SOW, etc.)

---

# PHASE 6 — LangGraph Pipeline (Core Orchestration)

File: `app/pipeline/graph_workflow.py`

This is the heart of the system. The entire document processing pipeline is a LangGraph `StateGraph`.

## Step 6.1: Define the state

```python
class PipelineState(TypedDict):
    file_path: str
    client_name: str
    project_name: str
    mapper_mode: str              # "rule" or "llm"

    document_id: str
    raw_text: str
    cleaned_text: str
    sections: list
    diffbot_results: list
    mapped_result: dict
    needs_review: bool
    review_items: list
    human_decisions: list
    ingestion_summary: dict

    status: str
    error: str
```

## Step 6.2: Define the nodes

Each node is a Python function that receives the state and returns a partial state update.

### Node: `load_and_preprocess`

```
Reads the file, extracts text, cleans it, splits into sections.
Updates: document_id, raw_text, cleaned_text, sections
```

### Node: `extract_with_diffbot`

```
Sends each section to Diffbot NLP API, caches results.
Updates: diffbot_results
```

### Node: `map_entities` (conditional — routes to rule OR llm based on `mapper_mode`)

**Sub-node: `map_with_rules`**

```
Runs rule_mapper.map_document_rule_based()
Updates: mapped_result
```

**Sub-node: `map_with_llm`**

```
Runs llm_mapper.map_document_llm_based()
Updates: mapped_result
```

### Node: `validate_and_check`

```
Validates mapped_result against ontology schema.
Checks: required fields, relationship direction, duplicate detection.
Identifies items needing review (unmapped entities, low confidence scores).
Updates: needs_review, review_items
```

### Node: `human_review` (conditional — only if `needs_review` is True)

```
Uses LangGraph's `interrupt()` to pause the pipeline.
The UI displays review_items. User approves, edits, or rejects each.
When resumed, human_decisions are applied to mapped_result.
Updates: mapped_result (revised), human_decisions
```

### Node: `ingest_to_neo4j`

```
Loads the final mapped_result into Neo4j via LangChain Neo4jGraph.
Updates: ingestion_summary
```

## Step 6.3: Define the graph

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

def build_pipeline() -> StateGraph:
    builder = StateGraph(PipelineState)

    # Add nodes
    builder.add_node("load_and_preprocess", load_and_preprocess)
    builder.add_node("extract_with_diffbot", extract_with_diffbot)
    builder.add_node("map_with_rules", map_with_rules)
    builder.add_node("map_with_llm", map_with_llm)
    builder.add_node("validate_and_check", validate_and_check)
    builder.add_node("human_review", human_review)
    builder.add_node("ingest_to_neo4j", ingest_to_neo4j)

    # Edges
    builder.add_edge(START, "load_and_preprocess")
    builder.add_edge("load_and_preprocess", "extract_with_diffbot")

    # Conditional: route to rule or LLM mapper
    builder.add_conditional_edges(
        "extract_with_diffbot",
        lambda state: state["mapper_mode"],
        {"rule": "map_with_rules", "llm": "map_with_llm"},
    )

    builder.add_edge("map_with_rules", "validate_and_check")
    builder.add_edge("map_with_llm", "validate_and_check")

    # Conditional: route to human review or straight to ingestion
    builder.add_conditional_edges(
        "validate_and_check",
        lambda state: "human_review" if state["needs_review"] else "ingest",
        {"human_review": "human_review", "ingest": "ingest_to_neo4j"},
    )

    builder.add_edge("human_review", "ingest_to_neo4j")
    builder.add_edge("ingest_to_neo4j", END)

    # Compile with checkpointer for HITL
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer, interrupt_before=["human_review"])
```

## Step 6.4: Human-in-the-loop detail

When the pipeline hits the `human_review` node and `needs_review` is True:

1. LangGraph pauses execution (via `interrupt_before=["human_review"]`)
2. The pipeline state is saved to the checkpointer
3. The API returns the `review_items` to the UI
4. The user sees a table of flagged items in Streamlit with options:
   - **Approve**: accept the mapping as-is
   - **Edit**: change the node type or properties
   - **Reject**: discard the entity
5. The UI sends `human_decisions` back to the API
6. The API resumes the pipeline with `graph.update_state(thread_id, {"human_decisions": decisions})`
7. The `human_review` node applies the decisions to `mapped_result`
8. Pipeline continues to ingestion

### What gets flagged for review

| Condition                             | Source          |
| ------------------------------------- | --------------- |
| Unmapped entities (no ontology match) | Rule mapper     |
| Low confidence scores (< 0.7)         | LLM mapper      |
| Missing required properties           | Validation step |
| Potential duplicate entities          | Entity resolver |
| Unknown document type                 | Classifier      |

---

# PHASE 7 — Graph RAG (Natural Language → Cypher → Answer)

File: `app/rag/graph_rag.py`

Same as before — `GraphCypherQAChain` with few-shot Cypher examples.

```python
def create_graph_rag_chain(model_name="gpt-4o-mini"):
    graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USER, password=NEO4J_PASSWORD)
    llm = ChatOpenAI(model=model_name, temperature=0.0, api_key=OPENAI_API_KEY)

    chain = GraphCypherQAChain.from_llm(
        llm=llm, graph=graph,
        verbose=True,
        return_intermediate_steps=True,
        validate_cypher=True,
        cypher_prompt=few_shot_prompt,  # Few-shot examples
        top_k=20,
    )
    return chain

def ask(chain, question) -> dict:
    result = chain.invoke({"query": question})
    return {"question": question, "answer": result["result"], "cypher": ...}
```

### Few-shot examples included for:

- Find clauses changed by an amendment
- Get deliverables for a SOW
- List SOWs under a contract
- Show amendment lineage
- Compare pricing across engagements

---

# PHASE 8 — FastAPI Backend

File: `app/api/endpoints.py`

### Endpoints

| Method | Path                                        | Description                                      |
| ------ | ------------------------------------------- | ------------------------------------------------ |
| `POST` | `/api/v1/documents/upload`                  | Upload a document, start the pipeline            |
| `GET`  | `/api/v1/pipeline/{thread_id}/status`       | Get the current pipeline status for a thread     |
| `GET`  | `/api/v1/pipeline/{thread_id}/review-items` | Get items needing human review                   |
| `POST` | `/api/v1/pipeline/{thread_id}/review`       | Submit human review decisions, resume pipeline   |
| `POST` | `/api/v1/query`                             | Ask a natural language question (Graph RAG)      |
| `GET`  | `/api/v1/graph/stats`                       | Get graph statistics (node counts, labels, etc.) |

### How the HITL API flow works

```
1. POST /documents/upload  →  returns { thread_id, status: "running" }
2. Pipeline runs until human_review interrupt
3. GET /pipeline/{thread_id}/status  →  { status: "review", review_items: [...] }
4. POST /pipeline/{thread_id}/review  →  { decisions: [...] }
5. Pipeline resumes → ingests → returns { status: "completed", summary: {...} }
```

---

# PHASE 9 — Streamlit UI

File: `ui/streamlit_app.py`

### Pages / Tabs

#### Tab 1: Upload & Process

- File upload widget (PDF, DOCX)
- Text inputs for client name, project name
- **Mapper mode toggle**: radio button for "Rule-based" vs "LLM-based"
- "Process" button
- Progress bar showing pipeline stage
- Results summary after completion

#### Tab 2: Review Queue

- Table of flagged items from all running pipelines
- For each item:
  - Show the entity name, Diffbot type, suggested ontology type, confidence score
  - Show the source section text for context
  - Dropdown: select correct node type (or "Reject")
  - Editable fields for properties
- "Submit Review" button → resumes pipeline

#### Tab 3: Query

- Text input for natural language question
- "Ask" button
- Show: answer, generated Cypher query, raw result table
- Suggested questions sidebar

#### Tab 4: Graph Explorer

- Graph statistics (node counts, relationship counts per type)
- Run custom Cypher queries
- Display results as table

### Streamlit → FastAPI communication

The UI calls the FastAPI backend via `requests`:

```python
import requests
API_BASE = "http://localhost:8000/api/v1"

# Upload
resp = requests.post(f"{API_BASE}/documents/upload", files={"file": ...}, params={...})

# Check status
resp = requests.get(f"{API_BASE}/pipeline/{thread_id}/status")

# Submit review
resp = requests.post(f"{API_BASE}/pipeline/{thread_id}/review", json={"decisions": [...]})

# Ask question
resp = requests.post(f"{API_BASE}/query", params={"question": "..."})
```

---

# PHASE 10 — Configuration & Dependencies

## requirements.txt

```
# LangGraph orchestration
langgraph>=0.2.0
langchain>=0.2.0
langchain-community>=0.2.0
langchain-openai>=0.1.0

# Text extraction
pdfplumber>=0.10.0
python-docx>=1.0.0

# Diffbot API
requests>=2.31.0

# Entity resolution
rapidfuzz>=3.5.0

# Validation
pydantic>=2.5.0

# Graph database
neo4j>=5.15.0

# API
fastapi>=0.110.0
uvicorn>=0.27.0
python-multipart>=0.0.7

# UI
streamlit>=1.35.0

# Config
python-dotenv>=1.0.0
```

## .env.example

```
DIFFBOT_API_TOKEN=your_diffbot_token_here
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
OPENAI_API_KEY=your_openai_key_here
```

---

# PHASE 11 — Testing Strategy

| Test file                 | What it tests                                                           |
| ------------------------- | ----------------------------------------------------------------------- |
| `test_document_loader.py` | PDF/DOCX text extraction                                                |
| `test_preprocessor.py`    | Text cleaning, section detection                                        |
| `test_diffbot_client.py`  | API call, caching, chunking (mock API)                                  |
| `test_mapper.py`          | Both rule and LLM mappers, dedup, relationship building, classification |
| `test_neo4j_loader.py`    | Cypher generation, MERGE idempotency                                    |
| `test_graph_rag.py`       | Chain creation, Cypher generation from NL                               |

---

# PHASE 12 — MVP Execution Plan

## Milestone 1: Foundation

- Set up project structure
- Implement ontology, schemas, config
- Implement document loader + preprocessor + registry

## Milestone 2: Extraction

- Implement Diffbot client
- Test with real document, verify caching

## Milestone 3: Dual Mapper

- Implement rule_mapper.py
- Implement llm_mapper.py
- Implement entity_resolver.py + relationship_builder.py
- Write mapper tests for both modes

## Milestone 4: LangGraph Pipeline

- Implement graph_workflow.py with all nodes
- Wire conditional routing (mapper mode, human review)
- Test pipeline end-to-end without Neo4j

## Milestone 5: Neo4j

- Set up Neo4j (Docker or Aura)
- Implement neo4j_client.py + loader.py + queries.py
- Load mapped documents, verify in Neo4j Browser

## Milestone 6: Graph RAG

- Implement graph_rag.py with few-shot examples
- Test questions against loaded graph

## Milestone 7: API + UI

- Implement FastAPI endpoints
- Implement Streamlit UI (all 4 tabs)
- Test full flow: upload → process → review → query

---

# Appendix A: What We Are NOT Doing (Yet)

| Feature                      | Why deferred                                |
| ---------------------------- | ------------------------------------------- |
| Vector embeddings            | Not needed for structured graph queries     |
| Hybrid search                | Adds complexity without proving value first |
| Governance / RBAC            | Build after core pipeline works             |
| OCR for scanned PDFs         | Most enterprise docs are digital            |
| Versioning / change tracking | Build after graph has data to compare       |
| Multi-language support       | English pipeline first                      |

---

# Appendix B: Key Design Decisions

| Decision                           | Rationale                                                                                        |
| ---------------------------------- | ------------------------------------------------------------------------------------------------ |
| LangGraph for orchestration        | State machine with conditional edges, built-in HITL via interrupt, checkpointing for resume      |
| Dual mapper (rule + LLM)           | Rule-based is fast/free/deterministic; LLM handles edge cases. User picks from UI.               |
| Human-in-the-loop via interrupt    | Items flagged during validation pause the pipeline. User reviews in Streamlit, pipeline resumes. |
| LangChain Neo4jGraph for ingestion | Same connection object used for both writes and RAG queries. Consistent interface.               |
| Streamlit for UI                   | Fast to build, good for internal tools, supports tables/forms/file upload natively.              |
| Ontology defined before extraction | Prevents schema drift, ensures graph consistency                                                 |
| Section-level Diffbot extraction   | Better accuracy, enables traceability                                                            |
| Pydantic validation before write   | Catches bad data before it corrupts the graph                                                    |
| MERGE-based ingestion              | Idempotent — safe to re-run                                                                      |
| Cached Diffbot responses           | Saves API costs, audit trail                                                                     |

---

End of implementation plan v2.
