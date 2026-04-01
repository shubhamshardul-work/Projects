"""
Graph RAG — natural language → Cypher → answer.
Uses LangChain GraphCypherQAChain with few-shot examples.
This is the only part (besides optional LLM mapper) that calls an LLM.
"""

from __future__ import annotations

from langchain_community.graphs import Neo4jGraph
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
from langchain.chains import GraphCypherQAChain

from app.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from app.llm_factory import get_llm

# ---------------------------------------------------------------------------
# Few-shot Cypher examples
# ---------------------------------------------------------------------------

CYPHER_EXAMPLES = [
    {
        "question": "Which clauses were changed by amendment AMD-001?",
        "cypher": (
            "MATCH (a:Amendment {id: 'AMD-001'})-[:MODIFIES]->(cl:Clause) "
            "RETURN cl.clauseNumber, cl.title, cl.text"
        ),
    },
    {
        "question": "What are the deliverables for SOW-123?",
        "cypher": (
            "MATCH (s:SOW {id: 'SOW-123'})-[:HAS_DELIVERABLE]->(d:Deliverable) "
            "RETURN d.name, d.description, d.dueDate"
        ),
    },
    {
        "question": "Which SOWs belong to contract Contract-10?",
        "cypher": (
            "MATCH (c:Contract {id: 'Contract-10'})-[:HAS_SOW]->(s:SOW) "
            "RETURN s.id, s.title, s.startDate, s.endDate"
        ),
    },
    {
        "question": "Show me all milestones and their status for project PROJ-5",
        "cypher": (
            "MATCH (p:Project {id: 'PROJ-5'})-[:GOVERNED_BY]->(c:Contract)"
            "-[:HAS_SOW]->(s:SOW)-[:HAS_MILESTONE]->(m:Milestone) "
            "RETURN m.name, m.dueDate, m.status"
        ),
    },
    {
        "question": "What is the pricing model used in SOW-123?",
        "cypher": (
            "MATCH (s:SOW {id: 'SOW-123'})-[:USES_PRICING_MODEL]->(p:PricingModel) "
            "RETURN p.type, p.description, p.rateCard"
        ),
    },
    {
        "question": "Show the amendment lineage for SOW-200",
        "cypher": (
            "MATCH (s:SOW {id: 'SOW-200'})-[:REVISED_BY]->(a:Amendment) "
            "RETURN a.id, a.title, a.effectiveDate ORDER BY a.effectiveDate"
        ),
    },
]


def _build_few_shot_prompt() -> FewShotPromptTemplate:
    example_prompt = PromptTemplate(
        input_variables=["question", "cypher"],
        template="Question: {question}\nCypher: {cypher}",
    )
    return FewShotPromptTemplate(
        examples=CYPHER_EXAMPLES,
        example_prompt=example_prompt,
        prefix=(
            "You are a Neo4j Cypher expert. Given a question, generate a Cypher query.\n"
            "Here are some examples:\n"
        ),
        suffix="Question: {question}\nCypher:",
        input_variables=["question"],
    )


def create_graph_rag_chain(
    model_name: str | None = None,
) -> GraphCypherQAChain:
    """Build the Graph RAG chain with few-shot Cypher generation."""
    graph = Neo4jGraph(
        url=NEO4J_URI,
        username=NEO4J_USER,
        password=NEO4J_PASSWORD,
    )
    llm = get_llm(model=model_name) if model_name else get_llm()

    chain = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        verbose=True,
        return_intermediate_steps=True,
        validate_cypher=True,
        cypher_prompt=_build_few_shot_prompt(),
        top_k=20,
    )
    return chain


def ask(chain: GraphCypherQAChain, question: str) -> dict:
    """Ask a natural language question and get back answer + generated Cypher."""
    result = chain.invoke({"query": question})
    intermediate = result.get("intermediate_steps", [])
    cypher = intermediate[0].get("query", "") if intermediate else ""
    return {
        "question": question,
        "answer": result.get("result", ""),
        "cypher": cypher,
    }
