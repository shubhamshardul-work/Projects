import os
import sys

# Ensure we can import from the app folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.graph_db.neo4j_client import Neo4jClient

def test_neo4j_connection():
    print("Attempting to connect to Neo4j using Project_02's Neo4jClient...")
    
    try:
        # This initializes the LangChain Neo4jGraph under the hood
        # using the credentials from app.config (and .env)
        client = Neo4jClient()
        
        # Call the built-in verify_connectivity method
        client.verify_connectivity()
        print("\n✅ Successfully connected to Neo4j database!")
        
        # Try refreshing and fetching the schema as a deeper test
        try:
            client.refresh_schema()
            print("\nGraph Schema retrieved successfully:")
            print(client.schema)
        except Exception as schema_error:
            print(f"\nConnected, but failed to retrieve schema: {schema_error}")
            
    except Exception as e:
        print("\n❌ Failed to connect to Neo4j database.")
        print(f"Error Details: {e}")

if __name__ == "__main__":
    test_neo4j_connection()
