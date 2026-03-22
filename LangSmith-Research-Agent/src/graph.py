"""
LangGraph workflow for the AI Research Agent.

Demonstrates:
- StateGraph construction with conditional routing
- Trace hierarchy through graph nodes (visible in LangSmith)
- Conditional edges appearing as branching in trace trees
"""

from langgraph.graph import StateGraph, START, END
from src.state import ResearchState
from src.nodes import (
    router_node,
    search_node,
    retriever_node,
    grader_node,
    answer_node,
    formatter_node,
)


def _route_question(state: ResearchState) -> str:
    """Conditional edge function: routes based on router_node output."""
    route = state.get("route", "direct")
    if route == "search":
        return "search"
    elif route == "retrieve":
        return "retrieve"
    else:
        return "direct"


def build_graph():
    """
    Build the research agent graph.
    
    Flow:
        START → router → [search | retriever | direct] → grader → answer → formatter → END
    
    The conditional routing appears as branching in LangSmith traces,
    making it easy to see which path was taken for each question.
    """
    builder = StateGraph(ResearchState)

    # Add nodes
    builder.add_node("router", router_node)
    builder.add_node("search", search_node)
    builder.add_node("retriever", retriever_node)
    builder.add_node("grader", grader_node)
    builder.add_node("answer", answer_node)
    builder.add_node("formatter", formatter_node)

    # Entry point
    builder.add_edge(START, "router")

    # Conditional routing based on router output
    builder.add_conditional_edges(
        "router",
        _route_question,
        {
            "search": "search",
            "retrieve": "retriever",
            "direct": "answer",  # Skip search/retriever for direct answers
        },
    )

    # After search or retrieval, grade the results
    builder.add_edge("search", "grader")
    builder.add_edge("retriever", "grader")

    # After grading, generate the answer
    builder.add_edge("grader", "answer")

    # Format and finish
    builder.add_edge("answer", "formatter")
    builder.add_edge("formatter", END)

    return builder.compile()
