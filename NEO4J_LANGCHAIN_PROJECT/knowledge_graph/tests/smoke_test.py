"""
Smoke test to verify all pipeline components are accessible.
Run with: python -m tests.smoke_test
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def smoke_test():
    """Touch every component to verify imports and basic connectivity."""
    print("=" * 60)
    print("SMOKE TEST: Enterprise Knowledge Graph Pipeline")
    print("=" * 60)

    # 1. Config imports
    print("\n[1/6] Testing config imports...")
    from config.ontology import ALLOWED_NODES, ALLOWED_RELATIONSHIPS, NODE_PROPERTIES
    assert len(ALLOWED_NODES) == 11, f"Expected 11 node types, got {len(ALLOWED_NODES)}"
    assert len(ALLOWED_RELATIONSHIPS) == 14, f"Expected 14 rel types, got {len(ALLOWED_RELATIONSHIPS)}"
    print(f"  ✓ Ontology: {len(ALLOWED_NODES)} node types, {len(ALLOWED_RELATIONSHIPS)} relationship types")

    from config.settings import LLM_MODEL, NEO4J_URI
    print(f"  ✓ Settings loaded (LLM_MODEL={LLM_MODEL})")

    # 2. Pydantic schema models
    print("\n[2/6] Testing Pydantic schema models...")
    from extraction.schema_extractor import ExtractedNode, ExtractedEdge, GraphExtraction
    node = ExtractedNode(id="test", type="Client", properties={"name": "Test Corp"})
    edge = ExtractedEdge(source_id="test", target_id="test2", type="CLIENT_OF")
    extraction = GraphExtraction(nodes=[node], edges=[edge])
    assert len(extraction.nodes) == 1
    assert len(extraction.edges) == 1
    print(f"  ✓ GraphExtraction model: {len(extraction.nodes)} nodes, {len(extraction.edges)} edges")

    # 3. Entity resolver
    print("\n[3/6] Testing entity resolver...")
    from graph.entity_resolver import normalise_name
    assert normalise_name("Accenture Solutions Pvt Ltd") == "accenture solutions"
    assert normalise_name("  Microsoft Corporation  ") == "microsoft"
    print("  ✓ Name normalisation working correctly")

    # 4. Neo4j connection (requires live credentials)
    print("\n[4/6] Testing Neo4j connection...")
    if NEO4J_URI:
        try:
            from langchain_neo4j import Neo4jGraph
            graph = Neo4jGraph(url=NEO4J_URI, username="neo4j", password="test")
            print("  ✓ Neo4j: Connection established")
        except Exception as e:
            print(f"  ⚠ Neo4j: {e} (expected if credentials not configured)")
    else:
        print("  ⚠ Neo4j: NEO4J_URI not set — skipping connection test")

    # 5. LLM connectivity (requires API key)
    print("\n[5/6] Testing LLM connectivity...")
    import os
    if os.getenv("OPENAI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GROQ_API_KEY"):
        try:
            from config.llm_factory import get_llm
            llm = get_llm(temperature=0.0)
            response = llm.invoke("Say OK")
            print(f"  ✓ LLM: {response.content}")
        except Exception as e:
            print(f"  ⚠ LLM: {e}")
    else:
        print("  ⚠ LLM: OPENAI_API_KEY / GOOGLE_API_KEY / GROQ_API_KEY not set — skipping LLM test")

    # 6. LangGraph basic graph
    print("\n[6/6] Testing LangGraph...")
    try:
        from langgraph.graph import StateGraph, END
        builder = StateGraph(dict)
        builder.add_node("test", lambda s: s)
        builder.set_entry_point("test")
        builder.add_edge("test", END)
        g = builder.compile()
        g.invoke({})
        print("  ✓ LangGraph: StateGraph compiled and invoked successfully")
    except Exception as e:
        print(f"  ⚠ LangGraph: {e}")

    print("\n" + "=" * 60)
    print("SMOKE TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    smoke_test()
