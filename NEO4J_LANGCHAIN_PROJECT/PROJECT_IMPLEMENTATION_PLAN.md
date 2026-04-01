# Enterprise Knowledge Graph — Full Implementation Plan

### Using Diffbot · LangGraph (LangChain) · Neo4j

**Document Type:** Senior Architect & Project Manager Reference  
**Scope:** End-to-end plan from problem statement to production-ready knowledge graph  
**Version:** 1.0

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Goals & Success Criteria](#2-goals--success-criteria)
3. [Tech Stack](#3-tech-stack)
4. [How We Are Solving This](#4-how-we-are-solving-this)
5. [Domain Ontology — The Schema Blueprint](#5-domain-ontology--the-schema-blueprint)
6. [Full Architecture](#6-full-architecture)
7. [Implementation Plan — Phase by Phase](#7-implementation-plan--phase-by-phase)
   - [Phase 1: Environment Setup](#phase-1-environment-setup)
   - [Phase 2: Document Ingestion & Chunking](#phase-2-document-ingestion--chunking)
   - [Phase 3: Diffbot NLP Extraction (Stage A)](#phase-3-diffbot-nlp-extraction-stage-a)
   - [Phase 4: Schema Mapping Bridge (Stage B)](#phase-4-schema-mapping-bridge-stage-b)
   - [Phase 5: Structured Output Schema Enforcement (Stage C)](#phase-5-structured-output-schema-enforcement-stage-c)
   - [Phase 6: Neo4j Write Layer (Stage D)](#phase-6-neo4j-write-layer-stage-d)
   - [Phase 7: LangGraph Orchestration — Wiring the Pipeline](#phase-7-langgraph-orchestration--wiring-the-pipeline)
   - [Phase 8: Entity Resolution & Deduplication](#phase-8-entity-resolution--deduplication)
   - [Phase 9: Query Layer & Business Insights](#phase-9-query-layer--business-insights)
   - [Phase 10: GraphRAG — Natural Language Interface](#phase-10-graphrag--natural-language-interface)
   - [Phase 11: Validation, Testing & Observability](#phase-11-validation-testing--observability)
   - [Phase 12: Production Hardening & Scheduling](#phase-12-production-hardening--scheduling)
8. [Project Timeline](#8-project-timeline)
9. [Risks & Mitigations](#9-risks--mitigations)
10. [Appendix — Key Code Reference](#10-appendix--key-code-reference)

---

## 1. Problem Statement

### 1.1 Context

A large consulting firm (structured like Accenture) manages hundreds of concurrent client engagements. Each engagement generates a corpus of unstructured and semi-structured documents:

- **Statements of Work (SOWs)** — define project scope, deliverables, timelines, commercial terms, penalties, and roles
- **Master Service Agreements (MSAs)** — govern the overarching legal relationship with a client
- **Change Orders / Amendments** — modifications to original SOWs: scope changes, budget revisions, timeline shifts
- **Project Plans / Schedules** — work breakdown structures, milestones, dependencies, assigned resources
- **Invoices & Purchase Orders** — financial transactions linking services rendered to contractual obligations
- **Meeting Notes & MoMs** — decisions, action items, risk flags, stakeholder positions
- **Staffing / Resource Plans** — who is assigned to what, at what billing rate, for how long
- **Risk Registers** — identified risks, ownership, mitigation plans
- **Delivery Reports / Status Updates** — progress against contractual commitments

### 1.2 The Core Problem

These documents exist in **silos**. They live in SharePoint folders, email attachments, project management tools, and finance systems. The knowledge locked inside them is:

- **Disconnected** — a risk flagged in a meeting note is not linked to the clause in the SOW that governs it
- **Non-traversable** — you cannot ask "show me every project that references the same penalty clause and find which ones are currently overrunning"
- **Person-dependent** — institutional knowledge lives in individuals' heads, not in a queryable system
- **Lineage-blind** — when a change order modifies a SOW, there is no automatic link; someone must manually know the history
- **Analytics-resistant** — patterns across hundreds of engagements (which clients over-amend, which project types carry the most risk, which people are single points of failure) are invisible without months of manual analysis

### 1.3 What Is Currently Not Possible

| Business Question                                                                    | Current State                                                 |
| ------------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| Which projects reference Clause 14.2 (penalty clause) and are currently overrunning? | Impossible without manual review of all contracts             |
| If a senior architect leaves, which active projects lose their only technical lead?  | Unknown — resource dependency is not tracked across documents |
| Which change orders were approved but never invoiced?                                | Requires cross-referencing finance and legal folders manually |
| Which client relationships have the highest rate of scope amendments?                | Not visible without manual counting across hundreds of SOWs   |
| What is the full contractual and financial history of Client X?                      | Requires opening dozens of documents manually                 |
| Which deliverables are blocked by unresolved risks?                                  | Invisible — risk registers and project plans are not linked   |

### 1.4 The Opportunity

If we can transform these documents into a **knowledge graph**, every one of the above questions becomes a Cypher query or a natural language question to a chatbot. The graph makes connections explicit, traversable, and auditable.

---

## 2. Goals & Success Criteria

### 2.1 Primary Goals

1. Build a **Neo4j knowledge graph** populated from all project documents in the firm
2. Capture entities, relationships, and properties according to a **predefined domain ontology**
3. Make the graph queryable via **Cypher**, **Graph Data Science**, and a **natural language chatbot** (GraphRAG)
4. Establish a **repeatable ingestion pipeline** so new documents auto-populate the graph
5. Provide full **document provenance** — every node must trace back to its source document and chunk

### 2.2 Success Criteria

| Criterion                                   | Target                            |
| ------------------------------------------- | --------------------------------- |
| Entity extraction precision                 | ≥ 85% on held-out test set        |
| Entity extraction recall                    | ≥ 80% on held-out test set        |
| Duplicate node rate after resolution        | < 5%                              |
| Graph population latency per document       | < 60 seconds                      |
| All predefined node types populated         | 100% coverage across 7 node types |
| Chatbot query accuracy on 50 test questions | ≥ 80% correct answers             |
| Source provenance linkable for every node   | 100%                              |

---

## 3. Tech Stack

### 3.1 Core Libraries & Packages

| Layer                        | Tool                       | Package                    | Purpose                                                                          |
| ---------------------------- | -------------------------- | -------------------------- | -------------------------------------------------------------------------------- |
| Document loading             | LangChain Loaders          | `langchain-community`      | Load PDF, DOCX, XLSX, MSG, SharePoint                                            |
| NLP extraction (Stage A)     | Diffbot NLP API            | `langchain-experimental`   | Heavy-lift entity + relation extraction, co-reference resolution, entity linking |
| Schema enforcement (Stage B) | Schema Enforcement | Structured Output Extraction using `langchain-openai` / `langchain-google-genai` + `pydantic` |
| Orchestration                | LangGraph                  | `langgraph`                | Stateful multi-agent pipeline as a directed graph                                |
| LLM backbone                 | Claude 3.5 Sonnet / GPT-4o | `anthropic` / `openai`     | Power structured schema extraction reasoning                                     |
| Graph database               | Neo4j                      | `langchain-neo4j`, `neo4j` | Store, index, and query the knowledge graph                                      |
| Vector search                | Neo4j Vector Index         | `langchain-neo4j`          | Embed chunks for semantic similarity and GraphRAG                                |
| Graph analytics              | Neo4j Graph Data Science   | `graphdatascience`         | Community detection, centrality, path analysis                                   |
| Natural language interface   | GraphCypherQAChain         | `langchain-neo4j`          | Translate natural language questions to Cypher                                   |
| Embeddings                   | OpenAI / Cohere            | `langchain-openai`         | Chunk and entity embeddings for vector index                                     |
| Observability                | LangSmith                  | `langsmith`                | Trace all LangGraph runs end-to-end                                              |

### 3.2 Install Commands

```bash
# Core pipeline
pip install langchain-experimental        # DiffbotGraphTransformer
pip install langchain-neo4j               # Neo4jGraph, Neo4jVector, GraphCypherQAChain
pip install langchain-community           # Document loaders (PDF, DOCX, XLSX, email)
pip install langchain-openai              # LLM + embeddings
pip install langgraph                     # StateGraph orchestration
pip install neo4j                         # Official Neo4j Python driver
pip install graphdatascience              # Neo4j GDS Python client
pip install langchain-google-genai        # Google Gemini LLM support

# Document parsing
pip install pypdf unstructured python-docx openpyxl

# Supporting utilities
pip install python-dotenv tenacity tqdm loguru
```

### 3.3 Neo4j Plugins Required

In Neo4j (AuraDB or self-hosted), ensure the following plugins are enabled:

- **APOC** — `apoc.merge.*` procedures for safe upserts
- **Graph Data Science (GDS)** — for analytics after population
- **Bloom** (optional) — for visual graph exploration

### 3.4 External APIs Required

| API                                | Purpose                      | Where to Obtain               |
| ---------------------------------- | ---------------------------- | ----------------------------- |
| Diffbot NLP API Token              | Entity + relation extraction | https://app.diffbot.com       |
| OpenAI API Key                     | LLM for structured schema extraction | https://platform.openai.com   |
| Google API Key                     | LLM for structured schema extraction | https://aistudio.google.com/app/apikey |
| Groq API Key                       | Fast LLM inference (e.g., Llama 3) | https://console.groq.com/keys |
| Neo4j Connection URI + Credentials | Graph database               | https://neo4j.com/cloud/aura/ |
| LangSmith API Key                  | Pipeline observability       | https://smith.langchain.com   |

---

## 4. How We Are Solving This

### 4.1 The Core Insight

The problem with building a domain-specific knowledge graph from documents is a **two-stage extraction problem**:

**Stage A — Raw extraction (what's in the text?)**  
Raw NLP: who are the people? what organisations? what dates? what monetary values? what relationships exist between them? This is hard to do well — it requires co-reference resolution ("he" = "John Smith"), entity linking (knowing "MS" and "Microsoft" are the same node), and relation extraction at scale. **This is exactly what Diffbot's NLP API does. We let Diffbot do this heavy lifting.**

**Stage B — Schema enforcement (what does it mean in our domain?)**  
Diffbot uses its own generic taxonomy: `Organization`, `Person`, `Location`, `Product`. It has no concept of `:SOW`, `:ChangeOrder`, `:Deliverable`, or `:Risk`. After Diffbot extracts rich entity and relationship context, we pass that enriched content to an **LLM with Pydantic structured output** (`ChatOpenAI`, `ChatGoogleGenerativeAI`, or `ChatGroq`), which re-maps it to **our predefined domain ontology** — controlling exactly which node types, relationship types, and properties are created in Neo4j. The LLM's reasoning capability is what bridges the semantic gap, and Pydantic schema enforcement guarantees the output strictly conforms to our ontology.

**The bridge between Stage A and Stage B** is a LangGraph node that serialises Diffbot's `GraphDocument` objects back into enriched `Document` objects (with the extracted facts embedded as structured context), so the structured output LLM has both the raw text AND Diffbot's pre-extracted knowledge to work from.

Using an LLM alone on raw documents (as the now-deprecated `LLMGraphTransformer` did) would work, but at a cost:

- **LLM calls are expensive** — processing 100,000-word documents chunk by chunk with an LLM is slow and costly
- **LLMs hallucinate entity links** — they may miss that "Rahul Mehta" in the SOW and "R. Mehta" in meeting notes are the same person
- **No Wikidata anchoring** — without Diffbot's entity linking, the same organisation could become multiple nodes

Diffbot solves all three problems cheaply. The LLM then only does the high-reasoning work of schema mapping via structured output, not raw text scanning.

### 4.2 Pipeline Stages & Mapping

| Stage | Neo4j/Diffbot Concept | Implementation Mapping |
| :--- | :--- | :--- |
| **A** | NLP Extraction | `DiffbotGraphTransformer` (generic entities + rels) |
| **B** | Schema Enforcement | Pydantic + `ChatOpenAI`/`ChatGoogleGenerativeAI(with_structured_output)` |
| **C** | Graph Storage | Neo4j `MERGE` queries (idempotent upserts) |
| **D** | Analytics/RAG | `GraphCypherQAChain` + `Neo4jVector` |

### 4.3 Why Not Just Use Diffbot Directly?

`DiffbotGraphTransformer` writes to Neo4j using its own schema. You end up with a graph full of `:Organization` and `:Person` nodes and generic `AGENT_OF` relationships — with no concept of your firm's domain structure. You cannot then query "find all projects where the deliverable owner is also the risk owner."

### 4.4 Why LangGraph?

The pipeline is not a linear chain — it's a directed graph of decisions:

- Some documents need retry (Diffbot API timeout)
- Some extractions are ambiguous and need a human-in-the-loop node
- Some documents are duplicates and need short-circuit routing
- Different document types need different extraction configurations

LangGraph's `StateGraph` handles all of this natively with conditional edges, state persistence, and checkpointing.

---

## 5. Domain Ontology — The Schema Blueprint

> **This section is the most important in the entire document. Define this carefully before writing any code. Everything downstream depends on it.**

### 5.1 Node Types

| Node Label      | Description                                              | Key Properties                                                                     |
| --------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `:Client`       | The external organisation the firm is serving            | `name`, `industry`, `region`, `canonical_id` (Wikidata URI from Diffbot)           |
| `:Project`      | A specific engagement / delivery                         | `project_id`, `name`, `status`, `start_date`, `end_date`, `total_value`            |
| `:Person`       | Any individual — employee, client contact, subcontractor | `name`, `role`, `email`, `employer`, `canonical_id`                                |
| `:SOW`          | Statement of Work document                               | `doc_id`, `title`, `effective_date`, `expiry_date`, `contract_value`, `currency`   |
| `:Deliverable`  | A specific output committed to in an SOW                 | `name`, `due_date`, `status`, `acceptance_criteria`                                |
| `:Milestone`    | A time-bound checkpoint in a project                     | `name`, `due_date`, `status`                                                       |
| `:ChangeOrder`  | A formal amendment to an SOW                             | `doc_id`, `amendment_number`, `change_description`, `value_delta`, `approved_date` |
| `:Invoice`      | A billing document                                       | `invoice_id`, `amount`, `currency`, `invoice_date`, `payment_status`               |
| `:Risk`         | An identified project or contractual risk                | `description`, `severity`, `category`, `status`, `mitigation`                      |
| `:Clause`       | A specific clause in a contract with legal significance  | `clause_number`, `title`, `category`, `verbatim_text`                              |
| `:BusinessUnit` | Internal division responsible for the engagement         | `name`, `practice_area`, `geography`                                               |
| `:Document`     | Source document node (for provenance)                    | `doc_id`, `file_name`, `doc_type`, `ingestion_date`, `file_path`                   |
| `:Chunk`        | A text chunk from a document (for vector search)         | `chunk_id`, `text`, `embedding`, `page_number`                                     |

### 5.2 Relationship Types

| Relationship        | From → To                    | Description                               |
| ------------------- | ---------------------------- | ----------------------------------------- |
| `SIGNED_BY`         | `:SOW` → `:Person`           | Who authorised the SOW                    |
| `GOVERNS`           | `:SOW` → `:Project`          | Which SOW governs which project           |
| `AMENDED_BY`        | `:SOW` → `:ChangeOrder`      | Change orders modifying a base SOW        |
| `HAS_DELIVERABLE`   | `:Project` → `:Deliverable`  | Deliverables committed in a project       |
| `HAS_MILESTONE`     | `:Project` → `:Milestone`    | Milestones in a project                   |
| `HAS_RISK`          | `:Project` → `:Risk`         | Risks identified for a project            |
| `RESPONSIBLE_FOR`   | `:Person` → `:Deliverable`   | Who owns a deliverable                    |
| `ASSIGNED_TO`       | `:Person` → `:Project`       | Team members on a project                 |
| `BILLED_UNDER`      | `:Invoice` → `:SOW`          | Which SOW an invoice is raised against    |
| `BILLED_TO`         | `:Invoice` → `:Client`       | Which client receives an invoice          |
| `REFERENCES_CLAUSE` | `:Risk` → `:Clause`          | Risk tied to a specific contract clause   |
| `CONTAINS_CLAUSE`   | `:SOW` → `:Clause`           | Clauses within an SOW                     |
| `DELIVERED_BY`      | `:Project` → `:BusinessUnit` | Which BU is responsible                   |
| `CLIENT_OF`         | `:Project` → `:Client`       | Which client the project serves           |
| `MENTIONS`          | `:Chunk` → `:Node`           | Provenance — which chunk a node came from |
| `PART_OF`           | `:Chunk` → `:Document`       | Which document a chunk belongs to         |

### 5.3 Schema Representation (Cypher Constraints)

These constraints should be created in Neo4j before any data is written:

```cypher
-- Uniqueness constraints (create one per node type)
CREATE CONSTRAINT client_name IF NOT EXISTS
  FOR (c:Client) REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT project_id IF NOT EXISTS
  FOR (p:Project) REQUIRE p.project_id IS UNIQUE;

CREATE CONSTRAINT person_name IF NOT EXISTS
  FOR (p:Person) REQUIRE p.name IS UNIQUE;

CREATE CONSTRAINT sow_doc_id IF NOT EXISTS
  FOR (s:SOW) REQUIRE s.doc_id IS UNIQUE;

CREATE CONSTRAINT invoice_id IF NOT EXISTS
  FOR (i:Invoice) REQUIRE i.invoice_id IS UNIQUE;

CREATE CONSTRAINT document_id IF NOT EXISTS
  FOR (d:Document) REQUIRE d.doc_id IS UNIQUE;

CREATE CONSTRAINT chunk_id IF NOT EXISTS
  FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE;

-- Vector index for semantic search on chunks
CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
  FOR (c:Chunk) ON (c.embedding)
  OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};
```

---

## 6. Full Architecture

### 6.1 High-Level Overview

```
[Source Documents]
      │
      ▼
[Layer 1: Ingestion & Chunking]
  LangChain Loaders → Semantic Chunking → Metadata Tagging → Document Classification
      │
      ▼
[Layer 2: Stage A — DiffbotGraphTransformer]
  Entity Extraction → Co-reference Resolution → Entity Linking (Wikidata) → Fact Triples
  Output: GraphDocument objects (Diffbot's generic schema)
      │
      ▼
[Layer 3: Schema Mapping Bridge — LangGraph Node]
  Serialise GraphDocuments → Enriched LangChain Documents (structured context injected)
      │
      ▼
[Layer 4: Stage B — Structured Output Schema Extraction]
  Pydantic-constrained LLM extraction using with_structured_output()
  Output: Typed Pydantic objects matching YOUR domain ontology
      │
      ▼
[Layer 5: Stage C — Neo4j Write Layer]
  graph.add_graph_documents(include_source=True)
  MERGE nodes → MERGE relationships → Link chunks for provenance
      │
      ▼
[Neo4j Knowledge Graph]
  Nodes, Relationships, Properties, Vector Embeddings, Provenance Chains
      │
      ▼
[Layer 6: Query & Insight Layer]
  Cypher Queries │ Graph Data Science │ GraphRAG Chatbot │ NL → Cypher Chain
```

### 6.2 LangGraph Agent Graph (Detailed)

```
START
  │
  ▼
[ingest_node]
  Load document, parse, chunk, tag metadata, classify doc type
  │
  ├── if duplicate → [skip_node] → END
  │
  ▼
[diffbot_extraction_node]
  Call DiffbotGraphTransformer on each chunk
  Collect GraphDocument objects
  │
  ├── if API error → [retry_node] → back to diffbot_extraction_node (max 3 retries)
  │
  ▼
[bridge_node]
  Convert GraphDocuments → Enriched Documents
  Inject entity + relation context into page_content
  │
  ▼
[llm_schema_node]
  Call ChatOpenAI.with_structured_output(GraphExtraction)
  Output domain-schema typed Pydantic objects
  │
  ├── if low_confidence flag → [review_node] → human-in-loop approval → neo4j_write_node
  │
  ▼
[entity_resolution_node]
  Dedup nodes using canonical_id (Wikidata URI) + fuzzy name matching
  Merge duplicate nodes via APOC
  │
  ▼
[neo4j_write_node]
  graph.add_graph_documents(include_source=True)
  Write chunk embeddings to vector index
  │
  ▼
[validation_node]
  Verify node counts, relationship integrity, missing required properties
  Log results to LangSmith
  │
  ▼
END
```

---

## 7. Implementation Plan — Phase by Phase

---

### Phase 1: Environment Setup

**Objective:** Get all infrastructure running and verified before touching any documents.

#### Step 1.1 — Project Structure

Create the following directory layout:

```
knowledge_graph/
├── .env                          # All API keys and credentials
├── config/
│   ├── ontology.py               # Allowed nodes, relationships, properties
│   ├── settings.py               # All configuration constants
│   └── llm_factory.py            # LLM initialization for multi-provider support
├── ingestion/
│   ├── loaders.py                # LangChain document loaders per file type
│   ├── chunker.py                # Semantic chunking logic
│   └── classifier.py             # Document type classification
├── extraction/
│   ├── diffbot_extractor.py      # Stage A: DiffbotGraphTransformer wrapper
│   ├── bridge.py                 # GraphDocument → enriched Document conversion
│   └── schema_extractor.py      # Stage B: Pydantic structured output extraction
├── graph/
│   ├── neo4j_writer.py           # Stage C: Neo4j write operations
│   ├── constraints.py            # Cypher constraint creation scripts
│   ├── entity_resolver.py        # Dedup and merge logic
│   └── queries.py                # Reusable Cypher query library
├── pipeline/
│   ├── state.py                  # LangGraph GraphState TypedDict
│   ├── nodes.py                  # All LangGraph node functions
│   ├── graph.py                  # StateGraph assembly and compilation
│   └── runner.py                 # Entry point for running the pipeline
├── rag/
│   ├── cypher_chain.py           # GraphCypherQAChain setup
│   └── chatbot.py                # Natural language query interface
├── tests/
│   ├── test_extraction.py
│   ├── test_neo4j_writes.py
│   └── fixtures/                 # 20 sample annotated documents
└── notebooks/
    ├── 01_ontology_design.ipynb
    ├── 02_extraction_testing.ipynb
    └── 03_query_exploration.ipynb
```

#### Step 1.2 — Environment Variables

Create `.env` file:

```dotenv
# Diffbot
DIFFBOT_API_TOKEN=your_diffbot_token_here

# OpenAI (for structured schema extraction)
OPENAI_API_KEY=your_openai_key_here

# Google Gemini (for structured schema extraction)
GOOGLE_API_KEY=your_google_api_key_here

# Neo4j
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password_here

# LangSmith (observability)
LANGSMITH_API_KEY=your_langsmith_key_here
LANGSMITH_PROJECT=enterprise-knowledge-graph
LANGCHAIN_TRACING_V2=true

# Pipeline config
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
MAX_DIFFBOT_RETRIES=3
LLM_MODEL=gpt-4o # or gemini-1.5-pro
EMBEDDING_MODEL=text-embedding-3-small # or gemini-pro
```

#### Step 1.3 — Neo4j Instance Setup

1. Create a Neo4j AuraDB instance at https://neo4j.com/cloud/aura/
2. Select the **Enterprise** tier (required for GDS plugin)
3. Enable plugins: **APOC**, **Graph Data Science**
4. Download the connection credentials file
5. Test connectivity:

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
with driver.session() as session:
    result = session.run("RETURN 'Connection successful' AS message")
    print(result.single()["message"])
driver.close()
```

#### Step 1.4 — Create Neo4j Schema (Constraints & Indexes)

Run `graph/constraints.py`:

```python
from langchain_neo4j import Neo4jGraph

def create_schema(graph: Neo4jGraph):
    constraints = [
        "CREATE CONSTRAINT client_name IF NOT EXISTS FOR (c:Client) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:Project) REQUIRE p.project_id IS UNIQUE",
        "CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT sow_doc_id IF NOT EXISTS FOR (s:SOW) REQUIRE s.doc_id IS UNIQUE",
        "CREATE CONSTRAINT co_doc_id IF NOT EXISTS FOR (c:ChangeOrder) REQUIRE c.doc_id IS UNIQUE",
        "CREATE CONSTRAINT invoice_id IF NOT EXISTS FOR (i:Invoice) REQUIRE i.invoice_id IS UNIQUE",
        "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE",
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE",
    ]
    for cypher in constraints:
        graph.query(cypher)

    # Vector index for chunk embeddings
    graph.query("""
        CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
        FOR (c:Chunk) ON (c.embedding)
        OPTIONS {indexConfig: {
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine'
        }}
    """)
    print("Schema created successfully.")
```

#### Step 1.5 — Verify Full Stack

Write a smoke test that touches every component:

```python
# tests/smoke_test.py
def smoke_test():
    # 1. Neo4j connection
    from langchain_neo4j import Neo4jGraph
    graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)
    print("Neo4j: OK")

    # 2. Diffbot API
    import requests
    r = requests.post(
        "https://nl.diffbot.com/v3/analyze",
        params={"token": DIFFBOT_API_TOKEN},
        json={"content": "Accenture signed a 2 million dollar SOW with HDFC Bank.", "lang": "en"}
    )
    assert r.status_code == 200
    print("Diffbot: OK")

    # 3. LLM (OpenAI/Google)
    from config.llm_factory import get_llm
    llm = get_llm(temperature=0)
    response = llm.invoke("Say OK")
    print(f"LLM: {response.content}")

    # 4. LangGraph basic graph
    from langgraph.graph import StateGraph, END
    builder = StateGraph(dict)
    builder.add_node("test", lambda s: s)
    builder.set_entry_point("test")
    builder.add_edge("test", END)
    g = builder.compile()
    g.invoke({})
    print("LangGraph: OK")

smoke_test()
```

---

### Phase 2: Document Ingestion & Chunking

**Objective:** Load every document type the firm uses into standardised LangChain `Document` objects with rich metadata.

#### Step 2.1 — Document Loaders by File Type

```python
# ingestion/loaders.py
from pathlib import Path
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredExcelLoader,
    UnstructuredEmailLoader,
    TextLoader,
)
from langchain_core.documents import Document
from typing import List

LOADER_MAP = {
    ".pdf":  PyPDFLoader,
    ".docx": Docx2txtLoader,
    ".doc":  Docx2txtLoader,
    ".xlsx": UnstructuredExcelLoader,
    ".xls":  UnstructuredExcelLoader,
    ".msg":  UnstructuredEmailLoader,
    ".eml":  UnstructuredEmailLoader,
    ".txt":  TextLoader,
}

def load_document(file_path: str) -> List[Document]:
    """Load a single document file into LangChain Document objects."""
    ext = Path(file_path).suffix.lower()
    loader_cls = LOADER_MAP.get(ext)
    if not loader_cls:
        raise ValueError(f"Unsupported file type: {ext}")
    loader = loader_cls(file_path)
    docs = loader.load()
    # Inject base metadata
    for doc in docs:
        doc.metadata["file_path"] = file_path
        doc.metadata["file_name"] = Path(file_path).name
        doc.metadata["file_type"] = ext
    return docs

def load_directory(directory_path: str) -> List[Document]:
    """Recursively load all supported documents from a directory."""
    all_docs = []
    for path in Path(directory_path).rglob("*"):
        if path.suffix.lower() in LOADER_MAP:
            try:
                all_docs.extend(load_document(str(path)))
            except Exception as e:
                print(f"Failed to load {path}: {e}")
    return all_docs
```

#### Step 2.2 — Document Type Classification

Before chunking, classify each document so we can use it as metadata and apply type-specific chunking strategies:

```python
# ingestion/classifier.py
from langchain_core.documents import Document
from config.llm_factory import get_llm

DOC_TYPES = ["SOW", "MSA", "ChangeOrder", "Invoice", "ProjectPlan",
             "MeetingNotes", "RiskRegister", "ResourcePlan", "StatusReport", "Unknown"]

def classify_document(doc: Document) -> str:
    """Use LLM to classify document type from first 1500 characters."""
    llm = get_llm(temperature=0)
    snippet = doc.page_content[:1500]
    prompt = f"""You are classifying a corporate consulting document.
Based on the following excerpt, classify the document as one of:
{', '.join(DOC_TYPES)}

Respond with ONLY the document type label, nothing else.

Excerpt:
{snippet}
"""
    response = llm.invoke(prompt)
    doc_type = response.content.strip()
    if doc_type not in DOC_TYPES:
        doc_type = "Unknown"
    doc.metadata["doc_type"] = doc_type
    return doc_type
```

#### Step 2.3 — Semantic Chunking

```python
# ingestion/chunker.py
import hashlib
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from typing import List
import os

def chunk_document(doc: Document, use_semantic: bool = True) -> List[Document]:
    """
    Split a document into chunks.
    - Semantic chunking preferred (uses embeddings to find natural break points)
    - Falls back to recursive character splitting for very large docs
    """
    if use_semantic:
        embedding_model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        if "gemini" in embedding_model_name:
            embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model_name)
        else:
            embeddings = OpenAIEmbeddings(model=embedding_model_name)
        splitter = SemanticChunker(embeddings, breakpoint_threshold_type="percentile")
    else:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    chunks = splitter.split_documents([doc])

    # Assign stable chunk IDs based on content hash
    for i, chunk in enumerate(chunks):
        content_hash = hashlib.md5(chunk.page_content.encode()).hexdigest()[:12]
        chunk.metadata["chunk_id"] = f"{doc.metadata.get('file_name', 'doc')}_{i}_{content_hash}"
        chunk.metadata["chunk_index"] = i
        chunk.metadata["total_chunks"] = len(chunks)

    return chunks
```

#### Step 2.4 — Duplicate Detection

Before processing, check if a document has already been ingested:

```python
# ingestion/dedup.py
import hashlib

def get_document_hash(file_path: str) -> str:
    """Generate MD5 hash of file content for deduplication."""
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def is_already_ingested(doc_hash: str, graph) -> bool:
    """Check Neo4j for existing document with same hash."""
    result = graph.query(
        "MATCH (d:Document {content_hash: $hash}) RETURN count(d) AS cnt",
        params={"hash": doc_hash}
    )
    return result[0]["cnt"] > 0
```

---

### Phase 3: Diffbot NLP Extraction (Stage A)

**Objective:** Extract all entities, relations, and facts from each chunk using Diffbot's NLP API. This is the heavy-lifting stage.

#### Step 3.1 — DiffbotGraphTransformer Setup

```python
# extraction/diffbot_extractor.py
from langchain_experimental.graph_transformers.diffbot import DiffbotGraphTransformer
from langchain_core.documents import Document
from langchain_community.graphs.graph_document import GraphDocument
from typing import List
import time

def create_diffbot_transformer(api_token: str) -> DiffbotGraphTransformer:
    """
    Initialise DiffbotGraphTransformer.
    Note: DiffbotGraphTransformer extracts using Diffbot's own schema.
    Entities will be generic types: Person, Organization, etc.
    This is intentional — schema enforcement happens in Stage B.
    """
    return DiffbotGraphTransformer(diffbot_api_key=api_token)

def extract_with_diffbot(
    chunks: List[Document],
    transformer: DiffbotGraphTransformer,
    batch_size: int = 5,
    retry_limit: int = 3
) -> List[GraphDocument]:
    """
    Run DiffbotGraphTransformer on document chunks.
    Processes in small batches to respect API rate limits.
    Returns list of GraphDocument objects with Diffbot's extracted nodes and relationships.
    """
    all_graph_docs = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        for attempt in range(retry_limit):
            try:
                graph_docs = transformer.convert_to_graph_documents(batch)
                all_graph_docs.extend(graph_docs)
                time.sleep(0.5)  # Respect rate limits
                break
            except Exception as e:
                if attempt == retry_limit - 1:
                    print(f"Diffbot extraction failed after {retry_limit} attempts: {e}")
                else:
                    time.sleep(2 ** attempt)  # Exponential backoff

    return all_graph_docs
```

#### Step 3.2 — What Diffbot Returns

After this stage, for a chunk like:

> _"Rahul Mehta, Vice President at Accenture, signed the SOW dated 12 March 2024 with HDFC Bank for a total value of INR 4.5 crore covering the Core Banking Modernisation project."_

Diffbot will return a `GraphDocument` containing:

- **Nodes:** `Person(id="Rahul Mehta")`, `Organization(id="Accenture")`, `Organization(id="HDFC Bank")`
- **Relationships:** `EMPLOYEE_OF(Rahul Mehta → Accenture)`, `SIGNED_AGREEMENT(Rahul Mehta → HDFC Bank)`
- **Properties:** `date="2024-03-12"`, `value="INR 4.5 crore"`

These are in Diffbot's schema — not yours. That's fine. Stage B will re-map this.

---

### Phase 4: Schema Mapping Bridge (Stage B)

**Objective:** Convert Diffbot's `GraphDocument` objects into enriched `Document` objects that the structured output extractor can process. This is the critical handoff between Stage A and Stage B.

#### Step 4.1 — Bridge Logic

```python
# extraction/bridge.py
from langchain_community.graphs.graph_document import GraphDocument
from langchain_core.documents import Document
from typing import List

def graphdocs_to_enriched_documents(
    graph_docs: List[GraphDocument]
) -> List[Document]:
    """
    Convert Diffbot GraphDocuments into enriched LangChain Documents.

    Strategy:
    - Preserve the original chunk text (page_content)
    - Inject Diffbot's extracted entities and relationships as structured context
    - This gives the structured output extractor BOTH the raw text AND pre-extracted facts
    - The LLM can then perform high-quality schema mapping without re-scanning raw text

    This is the bridge between Diffbot's generic schema and your domain ontology.
    """
    enriched_docs = []

    for gd in graph_docs:
        # 1. Collect extracted entity descriptions
        entity_lines = []
        for node in gd.nodes:
            props = ", ".join([f"{k}={v}" for k, v in node.properties.items()])
            entity_lines.append(
                f"ENTITY: {node.id} | Type: {node.type}"
                + (f" | Properties: {props}" if props else "")
            )

        # 2. Collect extracted relationship descriptions
        rel_lines = []
        for rel in gd.relationships:
            rel_lines.append(
                f"RELATION: {rel.source.id} --[{rel.type}]--> {rel.target.id}"
            )

        # 3. Build enriched content block
        enriched_content = gd.source.page_content

        if entity_lines or rel_lines:
            enriched_content += "\n\n--- EXTRACTED CONTEXT (from NLP pre-processing) ---\n"
            if entity_lines:
                enriched_content += "\nIdentified entities:\n" + "\n".join(entity_lines)
            if rel_lines:
                enriched_content += "\n\nIdentified relationships:\n" + "\n".join(rel_lines)

        enriched_doc = Document(
            page_content=enriched_content,
            metadata={
                **gd.source.metadata,
                "diffbot_node_count": len(gd.nodes),
                "diffbot_rel_count": len(gd.relationships),
                "bridge_processed": True
            }
        )
        enriched_docs.append(enriched_doc)

    return enriched_docs
```

---

### Phase 5: Structured Output Schema Enforcement (Stage C)

**Objective:** Use Pydantic models with `ChatOpenAI.with_structured_output()` to extract entities and relationships that conform strictly to your domain ontology. This replaces the deprecated `LLMGraphTransformer` with a more reliable, maintainable approach.

> **Why not LLMGraphTransformer?**  
> `LLMGraphTransformer` from `langchain-experimental` has been deprecated and is no longer receiving updates or bug fixes. The recommended replacement is to use **Pydantic structured output** — it gives you strict schema enforcement, better reliability, full type safety, direct control over the extraction pipeline, and supports multiple providers natively (OpenAI, Gemini, etc.).

#### Step 5.1 — Ontology Configuration

```python
# config/ontology.py

ALLOWED_NODES = [
    "Client",
    "Project",
    "Person",
    "SOW",
    "Deliverable",
    "Milestone",
    "ChangeOrder",
    "Invoice",
    "Risk",
    "Clause",
    "BusinessUnit",
]

ALLOWED_RELATIONSHIPS = [
    "SIGNED_BY",
    "GOVERNS",
    "AMENDED_BY",
    "HAS_DELIVERABLE",
    "HAS_MILESTONE",
    "HAS_RISK",
    "RESPONSIBLE_FOR",
    "ASSIGNED_TO",
    "BILLED_UNDER",
    "BILLED_TO",
    "REFERENCES_CLAUSE",
    "CONTAINS_CLAUSE",
    "DELIVERED_BY",
    "CLIENT_OF",
]

NODE_PROPERTIES = {
    "Client":       ["name", "industry", "region", "canonical_id"],
    "Project":      ["project_id", "name", "status", "start_date", "end_date", "total_value"],
    "Person":       ["name", "role", "email", "employer", "canonical_id"],
    "SOW":          ["doc_id", "title", "effective_date", "expiry_date", "contract_value", "currency"],
    "Deliverable":  ["name", "due_date", "status", "acceptance_criteria"],
    "Milestone":    ["name", "due_date", "status"],
    "ChangeOrder":  ["doc_id", "amendment_number", "change_description", "value_delta", "approved_date"],
    "Invoice":      ["invoice_id", "amount", "currency", "invoice_date", "payment_status"],
    "Risk":         ["description", "severity", "category", "status", "mitigation"],
    "Clause":       ["clause_number", "title", "category"],
    "BusinessUnit": ["name", "practice_area", "geography"],
}
```

#### Step 5.2 — Pydantic Schema Models

```python
# extraction/schema_extractor.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from langchain_core.documents import Document
from config.ontology import ALLOWED_NODES, ALLOWED_RELATIONSHIPS, NODE_PROPERTIES
from config.llm_factory import get_llm_with_structured_output

# --- Pydantic models for structured output ---

class ExtractedNode(BaseModel):
    """A single entity extracted from the text, mapped to the domain ontology."""
    id: str = Field(..., description="Unique identifier for the entity (use the entity's name or canonical ID)")
    type: str = Field(..., description=f"One of: {', '.join(ALLOWED_NODES)}")
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Properties of the entity as key-value pairs"
    )

class ExtractedEdge(BaseModel):
    """A relationship between two entities, mapped to the domain ontology."""
    source_id: str = Field(..., description="ID of the source entity")
    target_id: str = Field(..., description="ID of the target entity")
    type: str = Field(..., description=f"One of: {', '.join(ALLOWED_RELATIONSHIPS)}")
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Properties of the relationship as key-value pairs"
    )

class GraphExtraction(BaseModel):
    """Complete graph extraction from a text chunk."""
    nodes: List[ExtractedNode] = Field(default_factory=list, description="Extracted entities")
    edges: List[ExtractedEdge] = Field(default_factory=list, description="Extracted relationships")
```

#### Step 5.3 — Structured Output Extraction

```python
# extraction/schema_extractor.py (continued)

EXTRACTION_SYSTEM_PROMPT = """You are an expert knowledge graph extraction engine for an enterprise consulting firm.

Given text about consulting projects, contracts, and business operations, extract entities and relationships
using ONLY the following predefined types.

ALLOWED NODE TYPES: {allowed_nodes}
ALLOWED RELATIONSHIP TYPES: {allowed_relationships}

RULES:
1. Extract ONLY node types from the allowed list — never use generic types like 'Organization' or 'Company'
2. Extract ONLY relationship types from the allowed list
3. Use the entity's name as the 'id' field
4. Include all relevant properties you can extract from the text
5. If you cannot confidently extract something, omit it — do not hallucinate
6. Map generic entities to domain types: 'Organization' → 'Client' or 'BusinessUnit', 'Agreement' → 'SOW'
""".format(
    allowed_nodes=", ".join(ALLOWED_NODES),
    allowed_relationships=", ".join(ALLOWED_RELATIONSHIPS),
)


def create_schema_extractor() -> callable:
    """
    Create a structured output extractor using Pydantic models.

    This replaces the deprecated LLMGraphTransformer. Instead of relying on
    langchain-experimental, we use structured output from an LLM provider:
    - Guarantees output conforms to the Pydantic schema
    - Uses OpenAI's native function calling / structured output mode
    - Gives strict type enforcement — no schema leakage
    - Is actively maintained and supported
    """
    llm = ChatOpenAI(model=model, temperature=0)
    return llm.with_structured_output(GraphExtraction)


def extract_with_structured_output(
    enriched_docs: List[Document],
    extractor: callable,
    batch_size: int = 10
) -> List[GraphExtraction]:
    """
    Run structured output extraction on Diffbot-enriched documents.
    Returns GraphExtraction objects conforming to your domain ontology.
    """
    all_extractions = []

    for i in range(0, len(enriched_docs), batch_size):
        batch = enriched_docs[i:i + batch_size]
        for doc in batch:
            try:
                extraction = extractor.invoke([
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": doc.page_content}
                ])
                # Validate: filter out any nodes/edges with disallowed types
                extraction.nodes = [n for n in extraction.nodes if n.type in ALLOWED_NODES]
                extraction.edges = [e for e in extraction.edges if e.type in ALLOWED_RELATIONSHIPS]
                all_extractions.append(extraction)
            except Exception as e:
                print(f"Structured output extraction failed for chunk: {e}")

    return all_extractions
```

#### Step 5.4 — What Structured Output Returns

Given the same chunk as before, after schema enforcement, the `GraphExtraction` will contain:

- **Nodes:** `ExtractedNode(id="SOW-HDFC-2024", type="SOW", properties={"effective_date": "2024-03-12", "contract_value": "4.5 crore", "currency": "INR"})`, `ExtractedNode(id="Rahul Mehta", type="Person", properties={"role": "Vice President", "employer": "Accenture"})`, `ExtractedNode(id="HDFC Bank", type="Client", properties={})`, `ExtractedNode(id="Core Banking Modernisation", type="Project", properties={})`
- **Edges:** `ExtractedEdge(source_id="SOW-HDFC-2024", target_id="Rahul Mehta", type="SIGNED_BY")`, `ExtractedEdge(source_id="Core Banking Modernisation", target_id="HDFC Bank", type="CLIENT_OF")`, `ExtractedEdge(source_id="SOW-HDFC-2024", target_id="Core Banking Modernisation", type="GOVERNS")`

These are typed Pydantic objects, ready to write to Neo4j via MERGE queries.

---

### Phase 6: Neo4j Write Layer (Stage D)

**Objective:** Persist the schema-compliant `GraphExtraction` objects (from structured output) to Neo4j with full source provenance, using MERGE queries for idempotent writes.

#### Step 6.1 — Neo4j Graph Writer

```python
# graph/neo4j_writer.py
from langchain_neo4j import Neo4jGraph
from extraction.schema_extractor import GraphExtraction
from langchain_openai import OpenAIEmbeddings
from typing import List
import os

def get_neo4j_graph() -> Neo4jGraph:
    return Neo4jGraph(
        url=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
    )

def write_extractions_to_neo4j(
    graph: Neo4jGraph,
    extractions: List[GraphExtraction],
    source_metadata: dict = None
) -> dict:
    """
    Write structured output extractions to Neo4j using MERGE patterns.

    For each extracted node, creates a node with the appropriate label and properties.
    For each extracted edge, creates a relationship between source and target nodes.
    Uses MERGE instead of CREATE for idempotent, safe upserts.
    """
    total_nodes = 0
    total_rels = 0

    for extraction in extractions:
        # Write nodes
        for node in extraction.nodes:
            # Build property SET clause dynamically
            props = {"id": node.id, **node.properties}
            set_clauses = ", ".join([f"n.{k} = ${k}" for k in props.keys()])
            query = f"MERGE (n:`{node.type}` {{id: $id}}) SET {set_clauses}"
            graph.query(query, params=props)
            total_nodes += 1

        # Write relationships
        for edge in extraction.edges:
            props = edge.properties or {}
            set_clause = ""
            if props:
                set_parts = ", ".join([f"r.{k} = ${k}" for k in props.keys()])
                set_clause = f" SET {set_parts}"
            query = f"""
                MATCH (a {{id: $source_id}}), (b {{id: $target_id}})
                MERGE (a)-[r:`{edge.type}`]->(b){set_clause}
            """
            params = {"source_id": edge.source_id, "target_id": edge.target_id, **props}
            graph.query(query, params=params)
            total_rels += 1

    return {
        "nodes_written": total_nodes,
        "relationships_written": total_rels,
        "extractions_processed": len(extractions),
    }

def write_chunk_embeddings(
    graph: Neo4jGraph,
    chunks: List,
    embeddings_model: OpenAIEmbeddings
) -> None:
    """
    Compute and store vector embeddings on :Chunk nodes.
    Required for vector similarity search and GraphRAG.
    """
    for chunk in chunks:
        embedding = embeddings_model.embed_query(chunk.page_content)
        graph.query(
            """
            MATCH (c:Chunk {chunk_id: $chunk_id})
            SET c.embedding = $embedding
            """,
            params={"chunk_id": chunk.metadata["chunk_id"], "embedding": embedding}
        )
```

#### Step 6.2 — Safe MERGE Patterns

When writing manually (outside `add_graph_documents`), always use MERGE:

```cypher
-- Safe upsert for a Client node
MERGE (c:Client {name: $name})
ON CREATE SET
    c.industry = $industry,
    c.region = $region,
    c.canonical_id = $canonical_id,
    c.created_at = datetime()
ON MATCH SET
    c.last_updated = datetime()
RETURN c;

-- Safe upsert for a relationship
MATCH (s:SOW {doc_id: $sow_id})
MATCH (p:Person {name: $person_name})
MERGE (s)-[r:SIGNED_BY]->(p)
ON CREATE SET r.created_at = datetime()
RETURN r;
```

---

### Phase 7: LangGraph Orchestration — Wiring the Pipeline

**Objective:** Assemble all the above nodes into a coherent, stateful, resumable pipeline using LangGraph's `StateGraph`.

#### Step 7.1 — State Definition

```python
# pipeline/state.py
from typing import TypedDict, List, Optional, Any
from langchain_core.documents import Document
from langchain_community.graphs.graph_document import GraphDocument
from extraction.schema_extractor import GraphExtraction

class GraphState(TypedDict):
    # Input
    file_path: str
    doc_hash: str

    # After ingestion
    raw_documents: List[Document]
    doc_type: str
    chunks: List[Document]

    # After Diffbot
    diffbot_graph_docs: List[GraphDocument]

    # After bridge
    enriched_documents: List[Document]

    # After structured output extraction
    schema_extractions: List[GraphExtraction]

    # After resolution
    resolved_extractions: List[GraphExtraction]

    # Write results
    write_stats: dict

    # Control flags
    is_duplicate: bool
    needs_review: bool
    retry_count: int
    errors: List[str]
```

#### Step 7.2 — Node Functions

```python
# pipeline/nodes.py
from pipeline.state import GraphState
from ingestion.loaders import load_document
from ingestion.chunker import chunk_document
from ingestion.classifier import classify_document
from ingestion.dedup import get_document_hash, is_already_ingested
from extraction.diffbot_extractor import create_diffbot_transformer, extract_with_diffbot
from extraction.bridge import graphdocs_to_enriched_documents
from extraction.schema_extractor import create_schema_extractor, extract_with_structured_output
from graph.neo4j_writer import get_neo4j_graph, write_extractions_to_neo4j, write_chunk_embeddings
from graph.entity_resolver import resolve_entities
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
import os

# Initialise shared resources once
llm = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=0)
diffbot_transformer = create_diffbot_transformer(os.getenv("DIFFBOT_API_TOKEN"))
schema_extractor = create_schema_extractor()
graph = get_neo4j_graph()
embeddings = OpenAIEmbeddings(model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))


def ingest_node(state: GraphState) -> GraphState:
    """Load, classify, deduplicate, and chunk the source document."""
    file_path = state["file_path"]
    doc_hash = get_document_hash(file_path)
    state["doc_hash"] = doc_hash

    if is_already_ingested(doc_hash, graph):
        state["is_duplicate"] = True
        return state

    raw_docs = load_document(file_path)
    doc_type = classify_document(raw_docs[0], llm)
    chunks = []
    for doc in raw_docs:
        chunks.extend(chunk_document(doc))

    state["raw_documents"] = raw_docs
    state["doc_type"] = doc_type
    state["chunks"] = chunks
    state["is_duplicate"] = False
    return state


def diffbot_extraction_node(state: GraphState) -> GraphState:
    """Run DiffbotGraphTransformer on chunks — Stage A extraction."""
    graph_docs = extract_with_diffbot(
        state["chunks"],
        diffbot_transformer,
        retry_limit=state.get("retry_count", 0) + 1
    )
    state["diffbot_graph_docs"] = graph_docs
    return state


def bridge_node(state: GraphState) -> GraphState:
    """Convert Diffbot GraphDocuments to enriched Documents for structured output extraction."""
    enriched = graphdocs_to_enriched_documents(state["diffbot_graph_docs"])
    state["enriched_documents"] = enriched
    return state


def llm_schema_node(state: GraphState) -> GraphState:
    """Run structured output extraction — Stage B schema enforcement."""
    extractions = extract_with_structured_output(
        state["enriched_documents"],
        schema_extractor
    )
    # Flag for review if extraction yield is very low
    total_nodes = sum(len(ext.nodes) for ext in extractions)
    state["schema_extractions"] = extractions
    state["needs_review"] = total_nodes == 0
    return state


def entity_resolution_node(state: GraphState) -> GraphState:
    """Deduplicate and merge entities across documents."""
    resolved = resolve_entities(state["schema_extractions"], graph)
    state["resolved_extractions"] = resolved
    return state


def neo4j_write_node(state: GraphState) -> GraphState:
    """Write resolved extractions to Neo4j with provenance."""
    stats = write_extractions_to_neo4j(graph, state["resolved_extractions"])
    write_chunk_embeddings(graph, state["chunks"], embeddings)
    state["write_stats"] = stats
    return state


def skip_node(state: GraphState) -> GraphState:
    """No-op node for duplicate documents."""
    print(f"Skipping duplicate document: {state['file_path']}")
    return state


def review_node(state: GraphState) -> GraphState:
    """Human-in-the-loop review for low-confidence extractions."""
    print(f"Document flagged for review: {state['file_path']}")
    print("Zero nodes extracted — manual review required before writing to graph.")
    # In production: send to a review queue (email, Slack, task system)
    return state
```

#### Step 7.3 — StateGraph Assembly

```python
# pipeline/graph.py
from langgraph.graph import StateGraph, END
from pipeline.state import GraphState
from pipeline.nodes import (
    ingest_node, diffbot_extraction_node, bridge_node,
    llm_schema_node, entity_resolution_node,
    neo4j_write_node, skip_node, review_node
)

def build_pipeline() -> StateGraph:
    """Assemble the full LangGraph pipeline."""
    builder = StateGraph(GraphState)

    # Register nodes
    builder.add_node("ingest", ingest_node)
    builder.add_node("diffbot_extract", diffbot_extraction_node)
    builder.add_node("bridge", bridge_node)
    builder.add_node("llm_schema", llm_schema_node)
    builder.add_node("entity_resolution", entity_resolution_node)
    builder.add_node("neo4j_write", neo4j_write_node)
    builder.add_node("skip", skip_node)
    builder.add_node("review", review_node)

    # Entry point
    builder.set_entry_point("ingest")

    # Conditional edge: skip duplicates
    builder.add_conditional_edges(
        "ingest",
        lambda state: "skip" if state["is_duplicate"] else "diffbot_extract"
    )

    # Linear flow: diffbot → bridge → llm_schema
    builder.add_edge("diffbot_extract", "bridge")
    builder.add_edge("bridge", "llm_schema")

    # Conditional edge: route low-confidence to review
    builder.add_conditional_edges(
        "llm_schema",
        lambda state: "review" if state["needs_review"] else "entity_resolution"
    )

    # Linear flow: resolution → write → end
    builder.add_edge("entity_resolution", "neo4j_write")
    builder.add_edge("neo4j_write", END)
    builder.add_edge("skip", END)
    builder.add_edge("review", END)

    return builder.compile()
```

#### Step 7.4 — Pipeline Runner

```python
# pipeline/runner.py
from pipeline.graph import build_pipeline
from pathlib import Path
from tqdm import tqdm
import json

def run_pipeline(file_paths: list, output_log: str = "pipeline_results.jsonl"):
    """Run the full pipeline on a list of file paths."""
    pipeline = build_pipeline()
    results = []

    for file_path in tqdm(file_paths, desc="Processing documents"):
        initial_state = {
            "file_path": str(file_path),
            "retry_count": 0,
            "errors": [],
            "needs_review": False,
            "is_duplicate": False,
        }
        try:
            final_state = pipeline.invoke(initial_state)
            results.append({
                "file": str(file_path),
                "status": "success",
                "doc_type": final_state.get("doc_type"),
                "write_stats": final_state.get("write_stats"),
            })
        except Exception as e:
            results.append({"file": str(file_path), "status": "error", "error": str(e)})

    with open(output_log, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    return results


if __name__ == "__main__":
    from pathlib import Path
    docs = list(Path("data/documents").rglob("*"))
    docs = [d for d in docs if d.is_file()]
    run_pipeline(docs)
```

---

### Phase 8: Entity Resolution & Deduplication

**Objective:** Ensure that the same real-world entity mentioned across multiple documents becomes a single node in the graph, not many duplicate nodes.

#### Step 8.1 — Why This Is Critical

Without resolution, "Microsoft Corporation", "Microsoft", and "MSFT" become three separate `:Client` nodes. Queries break. Analytics mislead.

#### Step 8.2 — Resolution Strategy

Use a three-tier approach:

1. **Wikidata URI matching** — Diffbot assigns canonical URIs (e.g., `https://www.wikidata.org/wiki/Q2283` for Microsoft). If two nodes have the same URI, they are definitively the same entity.
2. **Exact name normalisation** — lowercase, strip punctuation, strip legal suffixes ("Ltd", "Inc", "Pvt"): "Accenture Solutions Pvt Ltd" → "accenture solutions"
3. **Fuzzy name matching** — for remaining candidates, use edit distance (Levenshtein ≥ 0.85 similarity) as a candidate flag for human review

#### Step 8.3 — Resolution Code

```python
# graph/entity_resolver.py
from extraction.schema_extractor import GraphExtraction, ExtractedNode, ExtractedEdge
from langchain_neo4j import Neo4jGraph
from typing import List
import re

def normalise_name(name: str) -> str:
    """Normalise entity name for matching."""
    name = name.lower().strip()
    # Remove common legal suffixes
    suffixes = [" ltd", " limited", " inc", " llc", " pvt", " private", " corp", " corporation"]
    for suffix in suffixes:
        name = name.replace(suffix, "")
    # Remove punctuation
    name = re.sub(r"[^\w\s]", "", name)
    return name.strip()

def resolve_entities(
    extractions: List[GraphExtraction],
    graph: Neo4jGraph
) -> List[GraphExtraction]:
    """
    Pre-resolve entities before writing to Neo4j.
    Normalise node IDs so MERGE operations correctly deduplicate.
    """
    for extraction in extractions:
        for node in extraction.nodes:
            # Normalise name for consistent MERGE keys
            node.id = normalise_name(node.id)
            # Prefer canonical_id as the node key if Diffbot provided one
            if node.properties.get("canonical_id"):
                node.id = node.properties["canonical_id"]

        # Update edge source/target IDs to match normalised node IDs
        for edge in extraction.edges:
            edge.source_id = normalise_name(edge.source_id)
            edge.target_id = normalise_name(edge.target_id)

    return extractions

def merge_duplicate_nodes_in_neo4j(graph: Neo4jGraph):
    """
    Post-write APOC merge for any duplicates that slipped through.
    Requires APOC plugin enabled in Neo4j.
    """
    # Find nodes with same normalised name within the same label
    graph.query("""
        MATCH (a:Client), (b:Client)
        WHERE id(a) < id(b)
          AND toLower(trim(a.name)) = toLower(trim(b.name))
        CALL apoc.refactor.mergeNodes([a, b], {
            properties: 'combine',
            mergeRels: true
        })
        YIELD node
        RETURN count(node) AS merged
    """)
```

---

### Phase 9: Query Layer & Business Insights

**Objective:** Demonstrate the value of the knowledge graph through high-impact Cypher queries that answer business questions that were previously impossible.

#### Step 9.1 — Cypher Query Library

```cypher
-- Q1: Full contractual history of a client
MATCH (c:Client {name: "HDFC Bank"})<-[:CLIENT_OF]-(p:Project)
OPTIONAL MATCH (p)<-[:GOVERNS]-(s:SOW)
OPTIONAL MATCH (s)-[:AMENDED_BY]->(co:ChangeOrder)
OPTIONAL MATCH (i:Invoice)-[:BILLED_TO]->(c)
RETURN c, p, s, co, i
ORDER BY s.effective_date;

-- Q2: Key-person dependency risk
-- "If this person leaves, which active projects have NO other lead?"
MATCH (person:Person {name: "Rahul Mehta"})-[:RESPONSIBLE_FOR]->(d:Deliverable)<-[:HAS_DELIVERABLE]-(p:Project)
WHERE p.status = "Active"
WITH p, count(d) AS deliverables_owned
MATCH (p)<-[:RESPONSIBLE_FOR]-(other_person:Person)
WHERE other_person.name <> "Rahul Mehta"
WITH p, deliverables_owned, count(other_person) AS other_leads
WHERE other_leads = 0
RETURN p.name AS at_risk_project, deliverables_owned;

-- Q3: Revenue leakage — change orders not yet invoiced
MATCH (co:ChangeOrder)<-[:AMENDED_BY]-(s:SOW)<-[:BILLED_UNDER]-(i:Invoice)
WITH co, collect(i) AS invoices
WHERE size(invoices) = 0
RETURN co.doc_id, co.change_description, co.value_delta, co.approved_date
ORDER BY co.approved_date;

-- Q4: Projects referencing a high-risk clause
MATCH (cl:Clause {clause_number: "14.2"})<-[:REFERENCES_CLAUSE]-(r:Risk)<-[:HAS_RISK]-(p:Project)
WHERE p.status = "Active"
RETURN p.name, r.description, r.severity, r.status;

-- Q5: Cross-project pattern — clients with most amendments
MATCH (c:Client)<-[:CLIENT_OF]-(p:Project)<-[:GOVERNS]-(s:SOW)-[:AMENDED_BY]->(co:ChangeOrder)
RETURN c.name AS client, count(co) AS total_amendments
ORDER BY total_amendments DESC
LIMIT 10;

-- Q6: Deliverable provenance — which SOW clause defines this deliverable?
MATCH (d:Deliverable {name: "API Integration Module"})
MATCH (d)<-[:HAS_DELIVERABLE]-(p:Project)<-[:GOVERNS]-(s:SOW)-[:CONTAINS_CLAUSE]->(cl:Clause)
RETURN d.name, p.name, s.title, cl.clause_number, cl.title;

-- Q7: Find all people who have worked across multiple clients
MATCH (p:Person)-[:ASSIGNED_TO]->(proj:Project)-[:CLIENT_OF]->(c:Client)
WITH p, collect(DISTINCT c.name) AS clients
WHERE size(clients) > 1
RETURN p.name, p.role, clients
ORDER BY size(clients) DESC;
```

#### Step 9.2 — Graph Data Science Analytics

After populating the graph, run GDS algorithms for deeper insights:

```python
# graph/analytics.py
from graphdatascience import GraphDataScience

gds = GraphDataScience(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

# Project a graph for GDS
gds.graph.project(
    "project_network",
    ["Project", "Client", "Person", "Risk"],
    ["CLIENT_OF", "ASSIGNED_TO", "HAS_RISK"]
)

# PageRank — find most influential nodes (key clients, key people)
pagerank_result = gds.pageRank.stream("project_network")

# Community detection — discover natural project clusters
louvain_result = gds.louvain.stream("project_network")

# Betweenness centrality — find critical bridge people/projects
betweenness_result = gds.betweenness.stream("project_network")
```

---

### Phase 10: GraphRAG — Natural Language Interface

**Objective:** Allow non-technical stakeholders to query the knowledge graph in plain English.

#### Step 10.1 — GraphCypherQAChain Setup

```python
# rag/cypher_chain.py
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_openai import ChatOpenAI
import os

def build_cypher_chain() -> GraphCypherQAChain:
    graph = Neo4jGraph(
        url=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
    )
    # Refresh schema so the LLM knows the current graph structure
    graph.refresh_schema()

    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    chain = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        verbose=True,
        return_intermediate_steps=True,   # Return the generated Cypher for transparency
        allow_dangerous_requests=True      # Required flag in newer LangChain versions
    )
    return chain
```

#### Step 10.2 — Hybrid GraphRAG (Vector + Graph)

For questions that require reading document text AND traversing relationships:

```python
# rag/chatbot.py
from langchain_neo4j import Neo4jVector
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA

def build_graphrag_chain():
    """
    Hybrid retrieval: vector similarity on :Chunk nodes +
    graph traversal to bring in connected entity context.
    """
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    vector_store = Neo4jVector.from_existing_index(
        embedding=embeddings,
        url=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
        index_name="chunk_embedding",
        node_label="Chunk",
        text_node_property="text",
        embedding_node_property="embedding",
        retrieval_query="""
            MATCH (node:Chunk)-[:MENTIONS]->(entity)
            WITH node, score, collect(entity) AS related_entities
            RETURN node.text AS text,
                   score,
                   {
                     chunk_id: node.chunk_id,
                     doc_type: node.doc_type,
                     related_entities: [e IN related_entities | e.name]
                   } AS metadata
            ORDER BY score DESC
            LIMIT 10
        """
    )

    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vector_store.as_retriever(search_kwargs={"k": 10}),
        return_source_documents=True
    )
```

---

### Phase 11: Validation, Testing & Observability

**Objective:** Ensure the graph is correct, complete, and the pipeline is observable in production.

#### Step 11.1 — Extraction Quality Tests

```python
# tests/test_extraction.py
# Use 20 manually annotated documents as ground truth
# Compare extracted nodes/relationships against annotations
# Report precision, recall, F1 per entity type

def evaluate_extraction(test_docs, ground_truth, pipeline):
    for doc_path, expected in zip(test_docs, ground_truth):
        result = pipeline.invoke({"file_path": doc_path})
        extracted_nodes = {n.id for gd in result["schema_graph_docs"] for n in gd.nodes}
        expected_nodes = set(expected["nodes"])

        precision = len(extracted_nodes & expected_nodes) / len(extracted_nodes) if extracted_nodes else 0
        recall = len(extracted_nodes & expected_nodes) / len(expected_nodes) if expected_nodes else 0
        print(f"Doc: {doc_path} | Precision: {precision:.2f} | Recall: {recall:.2f}")
```

#### Step 11.2 — Graph Integrity Checks

```cypher
-- Check for orphan nodes (nodes with no relationships)
MATCH (n)
WHERE NOT (n)--()
  AND NOT n:Document
  AND NOT n:Chunk
RETURN labels(n), count(n) AS orphans;

-- Check for :Project nodes missing their :SOW relationship
MATCH (p:Project)
WHERE NOT (:SOW)-[:GOVERNS]->(p)
RETURN p.name AS projects_without_sow;

-- Check for :Chunk nodes missing provenance
MATCH (c:Chunk)
WHERE NOT (c)-[:PART_OF]->(:Document)
RETURN count(c) AS chunks_without_provenance;

-- Check property completeness on :SOW nodes
MATCH (s:SOW)
WHERE s.contract_value IS NULL OR s.effective_date IS NULL
RETURN s.doc_id, s.title AS incomplete_sows;
```

#### Step 11.3 — LangSmith Observability

All pipeline runs are automatically traced when `LANGCHAIN_TRACING_V2=true` is set. This gives you:

- Full trace of every agent node execution
- Token usage per LLM call
- Latency breakdown per pipeline step
- Error traces with full stack context

---

### Phase 12: Production Hardening & Scheduling

**Objective:** Make the pipeline production-grade — schedulable, resumable, and monitored.

#### Step 12.1 — Scheduled Ingestion

Use a scheduler (Apache Airflow or a simple cron) to watch for new documents and trigger the pipeline:

```python
# scheduler/watch_and_ingest.py
import time
from pathlib import Path
from pipeline.runner import run_pipeline
from ingestion.dedup import get_document_hash, is_already_ingested
from graph.neo4j_writer import get_neo4j_graph

WATCH_DIRECTORY = "data/incoming"
POLL_INTERVAL_SECONDS = 300  # Check every 5 minutes

graph = get_neo4j_graph()

def watch_and_process():
    while True:
        new_files = []
        for path in Path(WATCH_DIRECTORY).rglob("*"):
            if path.is_file():
                doc_hash = get_document_hash(str(path))
                if not is_already_ingested(doc_hash, graph):
                    new_files.append(str(path))

        if new_files:
            print(f"Found {len(new_files)} new documents. Processing...")
            run_pipeline(new_files)

        time.sleep(POLL_INTERVAL_SECONDS)
```

#### Step 12.2 — LangGraph Checkpointing for Resumability

```python
from langgraph.checkpoint.sqlite import SqliteSaver

# Enable checkpointing — if the pipeline crashes mid-run, resume from last checkpoint
checkpointer = SqliteSaver.from_conn_string("pipeline_checkpoints.db")
pipeline = build_pipeline().compile(checkpointer=checkpointer)

# Resume a failed run by its thread_id
pipeline.invoke(initial_state, config={"configurable": {"thread_id": "doc_12345"}})
```

#### Step 12.3 — Rate Limiting & Cost Controls

```python
# config/settings.py
import os

# Diffbot limits (check your plan)
DIFFBOT_MAX_REQUESTS_PER_MINUTE = 60
DIFFBOT_BATCH_SIZE = 5

# OpenAI cost controls
LLM_MAX_TOKENS_PER_CALL = 4096
EMBEDDING_BATCH_SIZE = 100

# Neo4j write batching
NEO4J_WRITE_BATCH_SIZE = 50

# Pipeline parallelism
MAX_CONCURRENT_DOCUMENTS = 3
```

---

## 8. Project Timeline

| Week | Phase    | Deliverable                                                               |
| ---- | -------- | ------------------------------------------------------------------------- |
| 1    | Phase 1  | Environment fully set up, smoke tests passing, Neo4j schema created       |
| 1–2  | Phase 2  | Ingestion pipeline working for all file types, chunking tested            |
| 2    | Phase 3  | Diffbot extraction tested on 20 sample documents, output reviewed         |
| 2–3  | Phase 4  | Bridge node implemented and verified, enriched documents inspected        |
| 3    | Phase 5  | Structured output extraction configured with full ontology, tested on same 20 docs |
| 3–4  | Phase 6  | Neo4j write layer working, constraints verified, provenance confirmed     |
| 4    | Phase 7  | Full LangGraph pipeline assembled and running end-to-end on test corpus   |
| 4–5  | Phase 8  | Entity resolution implemented, duplicate rate < 5%                        |
| 5    | Phase 9  | All 7 business-value Cypher queries working                               |
| 5–6  | Phase 10 | GraphRAG chatbot operational, tested on 50 questions                      |
| 6    | Phase 11 | Evaluation metrics passing, graph integrity checks clean                  |
| 6–7  | Phase 12 | Scheduler running, checkpointing enabled, LangSmith dashboard live        |

---

## 9. Risks & Mitigations

| Risk                                                    | Likelihood | Impact   | Mitigation                                                                                     |
| ------------------------------------------------------- | ---------- | -------- | ---------------------------------------------------------------------------------------------- |
| Diffbot API rate limits hit at scale                    | Medium     | High     | Batch processing, exponential backoff, request queuing                                         |
| Structured output extraction misses entities in long docs | High       | Medium   | Semantic chunking with overlap, multiple passes on key document types                          |
| Duplicate nodes pollute graph                           | High       | High     | Canonical ID from Diffbot, normalisation, APOC merge post-write                                |
| Confidential contract data in LLM prompts               | High       | Critical | Use Azure OpenAI with data residency, or a self-hosted LLM (Llama 3) for PII-sensitive content |
| Schema changes requiring graph migration                | Medium     | High     | Use versioned ontology file, APOC refactor procedures for schema evolution                     |
| Diffbot entity linking wrong for internal project names | High       | Medium   | Internal entity dictionary override — pre-populate known project/client names in Neo4j         |
| High LLM cost at scale (100K+ documents)                | Medium     | Medium   | Cache Diffbot results, only run structured extraction on high-value doc types first            |

---

## 10. Appendix — Key Code Reference

### Package Import Summary

```python
# Stage A — Diffbot extraction
from langchain_experimental.graph_transformers.diffbot import DiffbotGraphTransformer

# Stage B — Schema enforcement (Pydantic structured output)
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
# Usage: llm.with_structured_output(GraphExtraction)

# Neo4j graph operations
from langchain_neo4j import Neo4jGraph, Neo4jVector, GraphCypherQAChain

# LangGraph orchestration
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

# LLM + embeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# Document loading
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader

# Graph Data Science
from graphdatascience import GraphDataScience
```

### Key Design Decisions Summary

| Decision                                     | Rationale                                                                              |
| -------------------------------------------- | -------------------------------------------------------------------------------------- |
| Diffbot before structured output extraction  | Diffbot handles co-reference + entity linking cheaply; LLM handles schema mapping only |
| MERGE writes with Pydantic extraction output | Direct MERGE queries give full control over node/relationship creation                 |
| Pydantic structured output over LLMGraphTransformer | Deprecated library; structured output gives strict type safety and active support  |
| MERGE not CREATE for all writes              | Idempotent writes — safe to re-run pipeline on same documents                          |
| Semantic chunking over fixed-size            | Keeps semantically related sentences together — better extraction quality              |
| Canonical IDs from Wikidata (via Diffbot)    | Enables cross-document entity resolution without fuzzy matching overhead               |
| LangGraph over LangChain LCEL                | Native conditional routing, state persistence, checkpointing, human-in-loop            |

---

_End of Document_  
_Generated by: Senior Architect & Project Manager_  
_Framework: Diffbot · LangGraph · Neo4j_
