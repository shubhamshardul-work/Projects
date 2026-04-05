# 🔍 OrgGraph AI — Employee Intelligence GraphRAG

A **Graph-based RAG** system that ingests organizational employee data into **Neo4j** and enables natural language queries using **LangChain**, **LangGraph**, and a multi-provider LLM factory.

## Architecture

```
User Query → LangGraph Agent → Neo4j Knowledge Graph → Natural Language Answer
                  │
        ┌─────────┼────────────┐
        ▼         ▼            ▼
    Planner → Cypher Gen → Executor → Synthesizer
                               │
                     ┌─────────┼─────────┐
                     ▼         ▼         ▼
                   Groq    Gemini    OpenAI
                        (LLM Factory)
```

## Graph Schema

- **10 Node Types**: Employee, Skill, Project, Department, Office, CareerLevel, Certification, Training, Client, University
- **15+ Relationship Types**: HAS_SKILL, WORKS_IN, REPORTS_TO, ASSIGNED_TO, HOLDS_CERTIFICATION, and more
- **151 employees**, 40 skills, 15 projects, 100+ certifications, 450+ training records

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your Neo4j credentials and LLM API key
```

### 3. Ingest Data
```bash
python ingest.py
```

### 4. Launch Chat UI
```bash
streamlit run app.py
```

## LLM Providers

Set `LLM_PROVIDER` in `.env`:

| Provider | Env Var | Default Model |
|----------|---------|---------------|
| `groq` | `GROQ_API_KEY` | llama-3.3-70b-versatile |
| `gemini` | `GOOGLE_API_KEY` | gemini-2.0-flash |
| `openai` | `OPENAI_API_KEY` | gpt-4o-mini |

## Example Queries

- "Find Python experts with AWS certifications"
- "Who has worked on Banking projects with ML skills?"
- "Find available people for a project needing Python, Spark, and AWS"
- "Show top performers in the Data & AI department"
- "How many employees are in each department?"

## Project Structure

```
├── Source Input/          # Excel data
├── src/
│   ├── config.py          # Environment configuration
│   ├── llm_factory.py     # Multi-provider LLM factory
│   ├── data_loader.py     # Excel → DataFrames
│   ├── neo4j_manager.py   # Neo4j connection & queries
│   ├── ingestion/
│   │   └── ingest_graph.py  # DataFrame → Neo4j ingestion
│   ├── graph_rag/
│   │   ├── schema.py        # Graph schema for LLM context
│   │   ├── cypher_templates.py  # Few-shot Cypher examples
│   │   ├── prompts.py       # System prompts
│   │   └── agent.py         # LangGraph agent
│   └── utils/
│       └── logger.py        # Logging
├── app.py                 # Streamlit chat UI
├── ingest.py              # CLI ingestion entry point
└── requirements.txt
```
