from langgraph.graph import StateGraph, START, END
from src.state import AgentState
from src.nodes import tavily_node, rss_node, arxiv_node, github_node, hf_node, hn_node, reddit_node, youtube_node, aggregate_node, curate_node, summarize_node, email_node

def build_graph():
    builder = StateGraph(AgentState)
    
    # Add Nodes
    builder.add_node("tavily", tavily_node)
    builder.add_node("rss", rss_node)
    builder.add_node("arxiv", arxiv_node)
    builder.add_node("github", github_node)
    builder.add_node("hf", hf_node)
    builder.add_node("hn", hn_node)
    builder.add_node("reddit", reddit_node)
    builder.add_node("youtube", youtube_node)
    builder.add_node("aggregate", aggregate_node)
    
    builder.add_node("curate", curate_node)
    builder.add_node("summarize", summarize_node)
    builder.add_node("email", email_node)
    
    # Fan-out: Start all fetchers in parallel
    builder.add_edge(START, "tavily")
    builder.add_edge(START, "rss")
    builder.add_edge(START, "arxiv")
    builder.add_edge(START, "github")
    builder.add_edge(START, "hf")
    builder.add_edge(START, "hn")
    builder.add_edge(START, "reddit")
    builder.add_edge(START, "youtube")
    
    # Fan-in: Wait for all to finish, then aggregate
    builder.add_edge("tavily", "aggregate")
    builder.add_edge("rss", "aggregate")
    builder.add_edge("arxiv", "aggregate")
    builder.add_edge("github", "aggregate")
    builder.add_edge("hf", "aggregate")
    builder.add_edge("hn", "aggregate")
    builder.add_edge("reddit", "aggregate")
    builder.add_edge("youtube", "aggregate")
    
    # Process aggregated news
    builder.add_edge("aggregate", "curate")
    builder.add_edge("curate", "summarize")
    builder.add_edge("summarize", "email")
    builder.add_edge("email", END)
    
    return builder.compile()
