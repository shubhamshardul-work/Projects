"""
Neo4j schema constraint and index creation.
Run once before any data is written to ensure uniqueness and indexing.
"""

from langchain_neo4j import Neo4jGraph


def create_schema(graph: Neo4jGraph):
    """Create uniqueness constraints and vector indexes in Neo4j."""
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
        try:
            graph.query(cypher)
        except Exception as e:
            print(f"Constraint creation note: {e}")

    # Vector index for chunk embeddings
    try:
        graph.query("""
            CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
            FOR (c:Chunk) ON (c.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }}
        """)
    except Exception as e:
        print(f"Vector index creation note: {e}")

    print("Schema created successfully.")


if __name__ == "__main__":
    from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
    graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)
    create_schema(graph)
