"""
LangGraph nodes for the AI Research Agent.

Each node demonstrates specific LangSmith observability features:
- router_node:    @traceable + metadata + tags + ls_provider/ls_model_name
- search_node:    @traceable(run_type="tool") + cost tracking
- retriever_node: @traceable(run_type="retriever") + Document format
- grader_node:    @traceable(run_type="llm") + manual token tracking
- answer_node:    @traceable + thread tracking
- formatter_node: @traceable + custom run name
"""

import json
import os
import requests
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable, get_current_run_tree

from src.state import ResearchState
from src.rate_limiter import RateLimitedLLM


# ═══════════════════════════════════════════════════════════════════════════════
# Shared LLM instance (rate-limited, key-rotating)
# ═══════════════════════════════════════════════════════════════════════════════

_llm = None

def _get_llm() -> RateLimitedLLM:
    """Lazy-init a shared rate-limited LLM instance."""
    global _llm
    if _llm is None:
        _llm = RateLimitedLLM(
            model="gemini-2.5-flash",
            temperature=0,
            delay_seconds=5.0,
            max_retries=3,
        )
    return _llm


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 1: Router — decides which path to take
# ═══════════════════════════════════════════════════════════════════════════════
# LangSmith features: @traceable, metadata (ls_provider, ls_model_name,
#                     ls_temperature), tags, custom run name

@traceable(
    name="Route Question",
    tags=["router", "gemini-2.5-flash", "research-agent"],
    metadata={
        "ls_provider": "google_genai",
        "ls_model_name": "gemini-2.5-flash",
        "ls_temperature": 0,
        "node_type": "router",
        "description": "Routes the user question to search, retrieve, or direct answer",
    }
)
def router_node(state: ResearchState) -> dict:
    """
    Routes the user's question to the appropriate path.
    
    Demonstrates:
    - @traceable with custom name, tags, and metadata
    - ls_provider + ls_model_name for model identification in LangSmith UI
    - Rate-limited Gemini 2.5 Flash usage
    """
    question = state.get("question", "")
    llm = _get_llm()

    messages = [
        SystemMessage(content=(
            "You are a routing assistant. Given a user question, decide the best approach:\n"
            "- 'search': if the question needs current/real-time information from the web\n"
            "- 'retrieve': if the question is about a well-known topic that can be answered from documents\n"
            "- 'direct': if the question is simple enough to answer directly\n\n"
            "Reply with ONLY one word: search, retrieve, or direct."
        )),
        HumanMessage(content=question),
    ]

    response = llm.invoke(messages)
    route = response.content.strip().lower()

    # Normalize the route
    if "search" in route:
        route = "search"
    elif "retrieve" in route or "document" in route:
        route = "retrieve"
    else:
        route = "direct"

    print(f"[Router] Question: '{question[:60]}...' → Route: {route}")

    return {
        "route": route,
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 2: Web Search — fetches information from the web
# ═══════════════════════════════════════════════════════════════════════════════
# LangSmith features: @traceable(run_type="tool"), cost tracking via
#                     usage_metadata, custom tool metadata

@traceable(
    run_type="tool",
    name="Web Search",
    tags=["tool", "web-search"],
    metadata={
        "tool_name": "web_search",
        "description": "Searches the web for current information",
    }
)
def search_node(state: ResearchState) -> dict:
    """
    Simulates a web search tool.
    
    Demonstrates:
    - run_type="tool" for tool-specific rendering in LangSmith
    - Cost tracking for non-LLM runs via usage_metadata
    - Tool metadata for categorization
    """
    question = state.get("question", "")

    # Simulate a web search (using a simple Wikipedia API to avoid extra API keys)
    results = []
    try:
        # Use Wikipedia's search API as a free "web search"
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": question,
            "srlimit": 3,
            "format": "json",
            "utf8": 1,
        }
        response = requests.get(search_url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for item in data.get("query", {}).get("search", []):
                import re
                clean_snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
                results.append({
                    "title": item.get("title", ""),
                    "snippet": clean_snippet,
                    "url": f"https://en.wikipedia.org/wiki/{item.get('title', '').replace(' ', '_')}",
                    "source": "Wikipedia",
                })
    except Exception as e:
        print(f"[Search] Error: {e}")
        results = [{
            "title": "Search unavailable",
            "snippet": f"Could not search for: {question}",
            "url": "",
            "source": "error",
        }]

    # ── LangSmith: Track cost for this tool call ──
    # Demonstrates cost tracking on non-LLM runs
    try:
        run = get_current_run_tree()
        if run:
            run.extra = run.extra or {}
            run.extra["usage_metadata"] = {"total_cost": 0.0}  # Wikipedia is free!
    except Exception:
        pass

    print(f"[Search] Found {len(results)} results for: '{question[:50]}...'")

    return {"search_results": results}


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 3: Document Retriever — retrieves relevant documents
# ═══════════════════════════════════════════════════════════════════════════════
# LangSmith features: @traceable(run_type="retriever"), Document format
#                     for special retriever rendering in LangSmith UI

@traceable(
    run_type="retriever",
    name="Document Retriever",
    tags=["retriever", "knowledge-base"],
    metadata={
        "retriever_type": "simulated_vector_store",
        "k": 3,
    }
)
def retriever_node(state: ResearchState) -> dict:
    """
    Simulates a vector store retriever.
    
    Demonstrates:
    - run_type="retriever" for special document rendering in LangSmith
    - Returning documents in LangSmith's expected Document format
    - Retriever metadata (k, retriever type)
    """
    question = state.get("question", "")

    # Simulated knowledge base — demonstrates that LangSmith renders
    # retriever results with page_content + metadata in a rich UI
    knowledge_base = [
        {
            "page_content": (
                "Large Language Models (LLMs) are deep learning models trained on vast amounts "
                "of text data. They can generate human-like text, answer questions, summarize "
                "documents, and perform various natural language processing tasks."
            ),
            "type": "Document",
            "metadata": {
                "source": "ai_fundamentals.pdf",
                "page": 12,
                "chunk_id": "chunk_001",
                "relevance_score": 0.95,
            },
        },
        {
            "page_content": (
                "LangGraph is a framework for building stateful, multi-actor applications with "
                "LLMs. It extends LangChain with support for cycles, controllability, and "
                "persistence, making it ideal for building agent workflows."
            ),
            "type": "Document",
            "metadata": {
                "source": "langgraph_docs.pdf",
                "page": 1,
                "chunk_id": "chunk_042",
                "relevance_score": 0.91,
            },
        },
        {
            "page_content": (
                "Retrieval-Augmented Generation (RAG) combines information retrieval with "
                "text generation. It first retrieves relevant documents from a knowledge base, "
                "then uses an LLM to generate answers grounded in the retrieved context."
            ),
            "type": "Document",
            "metadata": {
                "source": "rag_patterns.pdf",
                "page": 5,
                "chunk_id": "chunk_017",
                "relevance_score": 0.88,
            },
        },
    ]

    print(f"[Retriever] Retrieved {len(knowledge_base)} documents for: '{question[:50]}...'")

    return {"retrieved_docs": knowledge_base}


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 4: Grader — evaluates document quality
# ═══════════════════════════════════════════════════════════════════════════════
# LangSmith features: @traceable with run_type="llm", manual token tracking
#                     via get_current_run_tree(), ls_model_name override

@traceable(
    run_type="llm",
    name="Document Grader",
    tags=["grader", "quality-check", "gemini-2.5-flash"],
    metadata={
        "ls_provider": "google_genai",
        "ls_model_name": "gemini-2.5-flash",
        "ls_temperature": 0,
        "ls_max_tokens": 1024,
        "node_type": "grader",
    }
)
def grader_node(state: ResearchState) -> dict:
    """
    Grades retrieved/searched documents for relevance.
    
    Demonstrates:
    - run_type="llm" for LLM-specific rendering (token counts, latency)
    - Manual token tracking via get_current_run_tree()
    - ls_model_name and ls_provider for cost tracking
    - Accessing and modifying the current run tree
    """
    question = state.get("question", "")

    # Combine search results and retrieved docs
    all_docs = []
    for doc in state.get("search_results", []):
        all_docs.append(f"[Search] {doc.get('title', '')}: {doc.get('snippet', '')}")
    for doc in state.get("retrieved_docs", []):
        all_docs.append(f"[Doc] {doc.get('page_content', '')[:200]}")

    if not all_docs:
        return {
            "graded_docs": [],
            "grade_reasoning": "No documents to grade.",
            "total_llm_calls": state.get("total_llm_calls", 0),
        }

    docs_text = "\n\n".join(all_docs[:5])  # Cap to 5 docs to save tokens

    llm = _get_llm()

    messages = [
        SystemMessage(content=(
            "You are a document relevance grader. Given a question and a set of documents, "
            "evaluate which documents are relevant to the question.\n\n"
            "Reply in JSON format: {\"relevant_indices\": [0, 1, ...], \"reasoning\": \"...\"}\n"
            "Only include indices of documents that are actually relevant."
        )),
        HumanMessage(content=f"Question: {question}\n\nDocuments:\n{docs_text}"),
    ]

    response = llm.invoke(messages)

    # ── LangSmith: Manual token tracking ──
    # Demonstrates attaching token usage to the run when the SDK
    # doesn't auto-populate it (e.g., custom models)
    try:
        run = get_current_run_tree()
        if run:
            # Estimate tokens (Gemini doesn't always return usage in LangChain)
            input_chars = len(str(messages))
            output_chars = len(response.content)
            est_input_tokens = input_chars // 4  # rough estimate
            est_output_tokens = output_chars // 4

            run.extra = run.extra or {}
            run.extra["usage_metadata"] = {
                "input_tokens": est_input_tokens,
                "output_tokens": est_output_tokens,
                "total_tokens": est_input_tokens + est_output_tokens,
            }
    except Exception:
        pass

    # Parse the grading result
    content = response.content.strip()
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            grade_result = json.loads(content[start:end])
        else:
            grade_result = {"relevant_indices": list(range(len(all_docs))), "reasoning": "Could not parse, including all."}
    except Exception:
        grade_result = {"relevant_indices": list(range(len(all_docs))), "reasoning": "Parse error, including all."}

    # Build graded docs list
    graded = []
    combined_source = state.get("search_results", []) + state.get("retrieved_docs", [])
    for idx in grade_result.get("relevant_indices", []):
        if idx < len(combined_source):
            graded.append(combined_source[idx])

    print(f"[Grader] {len(graded)}/{len(all_docs)} documents marked relevant")

    return {
        "graded_docs": graded,
        "grade_reasoning": grade_result.get("reasoning", ""),
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 5: Answer Generator — produces the final answer
# ═══════════════════════════════════════════════════════════════════════════════
# LangSmith features: @traceable with thread tracking metadata,
#                     feedback_run_id capture for later feedback submission

@traceable(
    name="Generate Answer",
    tags=["answer", "gemini-2.5-flash", "research-agent"],
    metadata={
        "ls_provider": "google_genai",
        "ls_model_name": "gemini-2.5-flash",
        "ls_temperature": 0.2,
        "node_type": "answer_generator",
    }
)
def answer_node(state: ResearchState) -> dict:
    """
    Generates the final research answer using graded context.
    
    Demonstrates:
    - Thread tracking via thread_id metadata (for multi-turn conversations)
    - Capturing feedback_run_id for asynchronous feedback submission
    - ls_temperature metadata for configuration tracking
    """
    question = state.get("question", "")
    thread_id = state.get("thread_id", "")

    # Build context from graded docs
    context_parts = []
    for doc in state.get("graded_docs", []):
        if "page_content" in doc:
            context_parts.append(doc["page_content"][:300])
        elif "snippet" in doc:
            context_parts.append(f"{doc.get('title', '')}: {doc.get('snippet', '')}")

    context = "\n\n".join(context_parts) if context_parts else "No specific context available."

    llm = _get_llm()

    messages = [
        SystemMessage(content=(
            "You are a knowledgeable research assistant. Answer the user's question "
            "based on the provided context. Be thorough but concise. "
            "If the context doesn't fully address the question, say so honestly and "
            "provide what you can based on your knowledge."
        )),
        HumanMessage(content=f"Question: {question}\n\nContext:\n{context}"),
    ]

    # ── LangSmith: Thread metadata for multi-turn tracking ──
    # This demonstrates how thread_id propagates to the trace
    langsmith_extra = {}
    if thread_id:
        langsmith_extra["metadata"] = {"thread_id": thread_id}

    response = llm.invoke(messages)

    # ── LangSmith: Capture run ID for later feedback ──
    feedback_run_id = ""
    try:
        run = get_current_run_tree()
        if run:
            feedback_run_id = str(run.id)
            # Also add thread metadata to the run
            if thread_id:
                run.metadata = run.metadata or {}
                run.metadata["thread_id"] = thread_id
    except Exception:
        pass

    print(f"[Answer] Generated answer ({len(response.content)} chars) for: '{question[:50]}...'")

    return {
        "answer": response.content,
        "feedback_run_id": feedback_run_id,
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 6: Formatter — formats the final report
# ═══════════════════════════════════════════════════════════════════════════════
# LangSmith features: @traceable with custom run name, no LLM call
#                     (pure function tracing), input/output logging

@traceable(
    name="Format Report",
    tags=["formatter", "output"],
    metadata={
        "node_type": "formatter",
        "output_format": "markdown",
    }
)
def formatter_node(state: ResearchState) -> dict:
    """
    Formats the answer into a structured markdown report.
    
    Demonstrates:
    - Tracing a pure function (no LLM) — shows up as a chain run
    - Custom run name for readable traces
    - Input/output logging for non-LLM processing steps
    """
    question = state.get("question", "")
    answer = state.get("answer", "No answer generated.")
    route = state.get("route", "unknown")
    grade_reasoning = state.get("grade_reasoning", "")
    graded_docs = state.get("graded_docs", [])
    total_calls = state.get("total_llm_calls", 0)

    # Build a structured markdown report
    report = f"""# 🔍 Research Report

## Question
{question}

## Route Selected
`{route}` — The router determined this question {"requires real-time web search" if route == "search" else "can be answered from the knowledge base" if route == "retrieve" else "can be answered directly"}.

## Relevant Sources ({len(graded_docs)} documents)
"""
    for i, doc in enumerate(graded_docs):
        if "page_content" in doc:
            source = doc.get("metadata", {}).get("source", "Unknown")
            report += f"\n### Source {i+1}: {source}\n{doc['page_content'][:200]}...\n"
        elif "title" in doc:
            report += f"\n### Source {i+1}: {doc['title']}\n{doc.get('snippet', doc.get('summary', ''))}\n"

    report += f"""
## Grading Reasoning
{grade_reasoning}

## Answer
{answer}

---
*Report generated by AI Research Agent | LLM calls: {total_calls} | Model: Gemini 2.5 Flash*
"""

    print(f"[Formatter] Generated report ({len(report)} chars)")

    return {"final_report": report}
