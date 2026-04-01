"""
GraphCypherQAChain setup for natural language to Cypher translation.
Allows non-technical users to query the knowledge graph in plain English.
"""

from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from config.llm_factory import get_llm

from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD


def build_cypher_chain() -> GraphCypherQAChain:
    """Build a GraphCypherQAChain for NL → Cypher query translation."""
    graph = Neo4jGraph(
        url=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
    )
    # Refresh schema so the LLM knows the current graph structure
    graph.refresh_schema()

    llm = get_llm(temperature=0.0)

    chain = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        verbose=True,
        return_intermediate_steps=True,
        allow_dangerous_requests=True
    )
    return chain


if __name__ == "__main__":
    chain = build_cypher_chain()
    # Example query
    result = chain.invoke({"query": "Which clients have the most change orders?"})
    print(result)
