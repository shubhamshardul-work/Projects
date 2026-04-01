"""
Hybrid GraphRAG chatbot.
Combines vector similarity search on Chunk nodes with graph traversal
for context-enriched answers.
"""

import os
from langchain_neo4j import Neo4jVector
from langchain.chains import RetrievalQA
from config.llm_factory import get_llm, get_embeddings

from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD


def build_graphrag_chain():
    """
    Hybrid retrieval: vector similarity on :Chunk nodes +
    graph traversal to bring in connected entity context.
    """
    embeddings = get_embeddings()

    vector_store = Neo4jVector.from_existing_index(
        embedding=embeddings,
        url=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
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

    llm = get_llm(temperature=0.0)

    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vector_store.as_retriever(search_kwargs={"k": 10}),
        return_source_documents=True
    )


if __name__ == "__main__":
    chain = build_graphrag_chain()
    result = chain.invoke({"query": "What are the key risks in the HDFC Bank project?"})
    print(result["result"])
