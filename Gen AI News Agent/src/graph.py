from langgraph.graph import StateGraph, START, END
from src.state import AgentState
from src.nodes import tavily_node, rss_node, arxiv_node, github_node, hf_node, aggregate_node, curate_node, summarize_node

def build_graph():
    builder = StateGraph(AgentState)
    
    # Add Nodes
    builder.add_node("tavily", tavily_node)
    builder.add_node("rss", rss_node)
    builder.add_node("arxiv", arxiv_node)
    builder.add_node("github", github_node)
    builder.add_node("hf", hf_node)
    builder.add_node("aggregate", aggregate_node)
    
    builder.add_node("curate", curate_node)
    builder.add_node("summarize", summarize_node)
    
    # Fan-out: Start all fetchers in parallel
    builder.add_edge(START, "tavily")
    builder.add_edge(START, "rss")
    builder.add_edge(START, "arxiv")
    builder.add_edge(START, "github")
    builder.add_edge(START, "hf")
    
    # Fan-in: Wait for all to finish, then aggregate
    builder.add_edge("tavily", "aggregate")
    builder.add_edge("rss", "aggregate")
    builder.add_edge("arxiv", "aggregate")
    builder.add_edge("github", "aggregate")
    builder.add_edge("hf", "aggregate")
    
    # Process aggregated news
    builder.add_edge("aggregate", "curate")
    builder.add_edge("curate", "summarize")
    builder.add_edge("summarize", END)
    
    return builder.compile()
