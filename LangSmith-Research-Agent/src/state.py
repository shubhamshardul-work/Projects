"""
State definition for the AI Research Agent graph.

Each field maps to a stage of the research pipeline, designed to
exercise different LangSmith tracing features at each node.
"""

from typing import TypedDict, List, Any, Optional


class ResearchState(TypedDict, total=False):
    """State flowing through the LangGraph research agent."""

    # --- Input ---
    question: str                      # User's research question
    thread_id: str                     # Thread ID for multi-turn conversation tracking

    # --- Router ---
    route: str                         # "search", "retrieve", or "direct"

    # --- Data Collection ---
    search_results: List[dict]         # Results from web search tool
    retrieved_docs: List[dict]         # Documents from vector retriever
    
    # --- Processing ---
    graded_docs: List[dict]            # Docs after quality grading
    grade_reasoning: str               # Grader's reasoning (for trace inspection)

    # --- Output ---
    answer: str                        # LLM-generated answer
    final_report: str                  # Formatted final report

    # --- LangSmith Metadata ---
    feedback_run_id: str               # Run ID for attaching feedback later
    total_llm_calls: int               # Counter for rate limit awareness
