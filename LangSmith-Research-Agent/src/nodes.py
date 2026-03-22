"""
LangGraph nodes for the AI Research Agent.

Each node demonstrates specific LangSmith observability features AND
captures REAL instrumentation data for the local logger:
- router_node:    @traceable + metadata + real timing + real tokens
- search_node:    @traceable(run_type="tool") + real HTTP timing
- retriever_node: @traceable(run_type="retriever") + Document format
- grader_node:    @traceable(run_type="llm") + real token tracking
- answer_node:    @traceable + thread tracking + real tokens
- formatter_node: @traceable + real timing
"""

import json
import os
import re
import time
import traceback as tb
import requests
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable, get_current_run_tree

from src.state import ResearchState
from src.rate_limiter import RateLimitedLLM


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
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


def _extract_usage(response) -> dict:
    """Extract REAL usage_metadata from an AIMessage response."""
    usage = {}
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        um = response.usage_metadata
        # LangChain's UsageMetadata can be a dict-like or object
        if isinstance(um, dict):
            usage = dict(um)
        else:
            usage = {
                "input_tokens": getattr(um, "input_tokens", None),
                "output_tokens": getattr(um, "output_tokens", None),
                "total_tokens": getattr(um, "total_tokens", None),
            }
            # Token detail breakdowns (cache_read, reasoning, etc.)
            if hasattr(um, "input_token_details") and um.input_token_details:
                details = um.input_token_details
                usage["input_token_details"] = dict(details) if isinstance(details, dict) else {
                    k: getattr(details, k) for k in dir(details)
                    if not k.startswith("_") and not callable(getattr(details, k))
                }
            if hasattr(um, "output_token_details") and um.output_token_details:
                details = um.output_token_details
                usage["output_token_details"] = dict(details) if isinstance(details, dict) else {
                    k: getattr(details, k) for k in dir(details)
                    if not k.startswith("_") and not callable(getattr(details, k))
                }
    return usage


def _extract_response_metadata(response) -> dict:
    """Extract REAL response_metadata from an AIMessage (finish_reason, safety, model)."""
    meta = {}
    if hasattr(response, "response_metadata") and response.response_metadata:
        rm = response.response_metadata
        meta = dict(rm) if isinstance(rm, dict) else {}
    return meta


def _serialize_messages(messages: list) -> list:
    """Convert LangChain Message objects to JSON-safe dicts."""
    result = []
    for msg in messages:
        if hasattr(msg, "content"):
            role = "system" if isinstance(msg, SystemMessage) else "human"
            result.append({"role": role, "content": msg.content})
        elif isinstance(msg, dict):
            result.append(msg)
    return result


def _append_trace(state: dict, trace_entry: dict) -> list:
    """Append a trace entry to the state's node_traces list."""
    traces = list(state.get("node_traces", []) or [])
    traces.append(trace_entry)
    return traces


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 1: Router — decides which path to take
# ═══════════════════════════════════════════════════════════════════════════════

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
    """Routes the user's question to the appropriate path."""
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

    error_info = None
    t0 = time.time()
    try:
        response = llm.invoke(messages)
    except Exception as e:
        error_info = tb.format_exc()
        raise
    latency_ms = round((time.time() - t0) * 1000, 2)

    route = response.content.strip().lower()
    if "search" in route:
        route = "search"
    elif "retrieve" in route or "document" in route:
        route = "retrieve"
    else:
        route = "direct"

    print(f"[Router] Question: '{question[:60]}...' → Route: {route}")

    # ── Build REAL trace entry ──
    usage = _extract_usage(response)
    resp_meta = _extract_response_metadata(response)

    trace_entry = {
        "node_name": "Route Question",
        "run_type": "llm",
        "latency_ms": latency_ms,
        "messages_sent": _serialize_messages(messages),
        "completion": response.content,
        "usage_metadata": usage,
        "response_metadata": resp_meta,
        "finish_reason": resp_meta.get("finish_reason"),
        "inputs": {"question": question},
        "outputs": {"route": route},
        "error": error_info,
        "tags": ["router", "gemini-2.5-flash", "research-agent"],
        "ls_metadata": {
            "ls_provider": "google_genai",
            "ls_model_name": "gemini-2.5-flash",
            "ls_temperature": 0,
            "ls_max_tokens": 10,
        },
        "status": "success",
    }

    return {
        "route": route,
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
        "node_traces": _append_trace(state, trace_entry),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 2: Web Search — fetches information from the web
# ═══════════════════════════════════════════════════════════════════════════════

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
    """Simulates a web search tool using Wikipedia API."""
    question = state.get("question", "")
    results = []
    http_status = None
    error_info = None

    t0 = time.time()
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": question,
            "srlimit": 3,
            "format": "json",
            "utf8": 1,
        }
        http_response = requests.get(search_url, params=params, timeout=10)
        http_status = http_response.status_code
        if http_response.status_code == 200:
            data = http_response.json()
            for item in data.get("query", {}).get("search", []):
                clean_snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
                results.append({
                    "title": item.get("title", ""),
                    "snippet": clean_snippet,
                    "url": f"https://en.wikipedia.org/wiki/{item.get('title', '').replace(' ', '_')}",
                    "source": "Wikipedia",
                })
    except Exception as e:
        error_info = tb.format_exc()
        print(f"[Search] Error: {e}")
        results = [{
            "title": "Search unavailable",
            "snippet": f"Could not search for: {question}",
            "url": "",
            "source": "error",
        }]
    latency_ms = round((time.time() - t0) * 1000, 2)

    # ── LangSmith: Track cost for this tool call ──
    try:
        run = get_current_run_tree()
        if run:
            run.extra = run.extra or {}
            run.extra["usage_metadata"] = {"total_cost": 0.0}
    except Exception:
        pass

    print(f"[Search] Found {len(results)} results for: '{question[:50]}...'")

    # ── Build REAL trace entry ──
    trace_entry = {
        "node_name": "Web Search",
        "run_type": "tool",
        "latency_ms": latency_ms,
        "inputs": {"query": question, "search_engine": "Wikipedia API", "max_results": 3},
        "outputs": {"results_count": len(results), "results": results},
        "error": error_info,
        "tags": ["tool", "web-search", "wikipedia"],
        "ls_metadata": {
            "tool_name": "web_search",
            "api_endpoint": "https://en.wikipedia.org/w/api.php",
            "http_status": http_status,
        },
        "status": "success" if not error_info else "error",
    }

    return {
        "search_results": results,
        "node_traces": _append_trace(state, trace_entry),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 3: Document Retriever — retrieves relevant documents
# ═══════════════════════════════════════════════════════════════════════════════

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
    """Simulates a vector store retriever with proper LangSmith Document format."""
    question = state.get("question", "")

    t0 = time.time()

    # Simulated knowledge base with proper LangSmith Document format
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

    latency_ms = round((time.time() - t0) * 1000, 2)

    print(f"[Retriever] Retrieved {len(knowledge_base)} documents for: '{question[:50]}...'")

    # ── Build REAL trace entry ──
    trace_entry = {
        "node_name": "Document Retriever",
        "run_type": "retriever",
        "latency_ms": latency_ms,
        "inputs": {"query": question, "k": 3, "retriever_type": "simulated_vector_store"},
        "outputs": {"documents_count": len(knowledge_base)},
        "retrieved_documents": knowledge_base,
        "error": None,
        "tags": ["retriever", "knowledge-base", "vector-store"],
        "ls_metadata": {
            "retriever_type": "simulated_vector_store",
            "k": 3,
            "embedding_model": "simulated",
        },
        "status": "success",
    }

    return {
        "retrieved_docs": knowledge_base,
        "node_traces": _append_trace(state, trace_entry),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 4: Grader — evaluates document quality
# ═══════════════════════════════════════════════════════════════════════════════

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
    """Grades retrieved/searched documents for relevance using REAL token tracking."""
    question = state.get("question", "")

    # Combine search results and retrieved docs
    all_docs = []
    for doc in state.get("search_results", []):
        all_docs.append(f"[Search] {doc.get('title', '')}: {doc.get('snippet', '')}")
    for doc in state.get("retrieved_docs", []):
        all_docs.append(f"[Doc] {doc.get('page_content', '')[:200]}")

    if not all_docs:
        trace_entry = {
            "node_name": "Document Grader",
            "run_type": "llm",
            "latency_ms": 0,
            "inputs": {"question": question, "documents_count": 0},
            "outputs": {"relevant_count": 0, "reasoning": "No documents to grade."},
            "error": None,
            "tags": ["grader", "quality-check", "gemini-2.5-flash"],
            "status": "success",
        }
        return {
            "graded_docs": [],
            "grade_reasoning": "No documents to grade.",
            "total_llm_calls": state.get("total_llm_calls", 0),
            "node_traces": _append_trace(state, trace_entry),
        }

    docs_text = "\n\n".join(all_docs[:5])
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

    error_info = None
    t0 = time.time()
    try:
        response = llm.invoke(messages)
    except Exception as e:
        error_info = tb.format_exc()
        raise
    latency_ms = round((time.time() - t0) * 1000, 2)

    # ── Extract REAL token data ──
    usage = _extract_usage(response)
    resp_meta = _extract_response_metadata(response)

    # ── LangSmith: Attach real usage to run tree ──
    try:
        run = get_current_run_tree()
        if run and usage:
            run.extra = run.extra or {}
            run.extra["usage_metadata"] = usage
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

    # ── Build REAL trace entry ──
    trace_entry = {
        "node_name": "Document Grader",
        "run_type": "llm",
        "latency_ms": latency_ms,
        "messages_sent": _serialize_messages(messages),
        "completion": response.content,
        "usage_metadata": usage,
        "response_metadata": resp_meta,
        "finish_reason": resp_meta.get("finish_reason"),
        "inputs": {"question": question, "documents_count": len(all_docs)},
        "outputs": {"relevant_count": len(graded), "reasoning": grade_result.get("reasoning", "")},
        "error": error_info,
        "tags": ["grader", "quality-check", "gemini-2.5-flash"],
        "ls_metadata": {
            "ls_provider": "google_genai",
            "ls_model_name": "gemini-2.5-flash",
            "ls_temperature": 0,
            "ls_max_tokens": 1024,
        },
        "status": "success",
    }

    return {
        "graded_docs": graded,
        "grade_reasoning": grade_result.get("reasoning", ""),
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
        "node_traces": _append_trace(state, trace_entry),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 5: Answer Generator — produces the final answer
# ═══════════════════════════════════════════════════════════════════════════════

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
    """Generates the final research answer with REAL token and timing data."""
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

    # ── LangSmith: Thread metadata ──
    if thread_id:
        try:
            run = get_current_run_tree()
            if run:
                run.metadata = run.metadata or {}
                run.metadata["thread_id"] = thread_id
        except Exception:
            pass

    error_info = None
    t0 = time.time()
    try:
        response = llm.invoke(messages)
    except Exception as e:
        error_info = tb.format_exc()
        raise
    latency_ms = round((time.time() - t0) * 1000, 2)

    # ── Extract REAL data ──
    usage = _extract_usage(response)
    resp_meta = _extract_response_metadata(response)

    # ── Capture feedback run ID ──
    feedback_run_id = ""
    try:
        run = get_current_run_tree()
        if run:
            feedback_run_id = str(run.id)
    except Exception:
        pass

    print(f"[Answer] Generated answer ({len(response.content)} chars) for: '{question[:50]}...'")

    # ── Build REAL trace entry ──
    trace_entry = {
        "node_name": "Generate Answer",
        "run_type": "llm",
        "latency_ms": latency_ms,
        "messages_sent": _serialize_messages(messages),
        "completion": response.content,
        "usage_metadata": usage,
        "response_metadata": resp_meta,
        "finish_reason": resp_meta.get("finish_reason"),
        "inputs": {"question": question, "context_length": len(context)},
        "outputs": {"answer_length": len(response.content), "answer": response.content},
        "error": error_info,
        "tags": ["answer", "gemini-2.5-flash", "research-agent"],
        "ls_metadata": {
            "ls_provider": "google_genai",
            "ls_model_name": "gemini-2.5-flash",
            "ls_temperature": 0.2,
        },
        "status": "success",
    }

    return {
        "answer": response.content,
        "feedback_run_id": feedback_run_id,
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
        "node_traces": _append_trace(state, trace_entry),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 6: Formatter — formats the final report
# ═══════════════════════════════════════════════════════════════════════════════

@traceable(
    name="Format Report",
    tags=["formatter", "output"],
    metadata={
        "node_type": "formatter",
        "output_format": "markdown",
    }
)
def formatter_node(state: ResearchState) -> dict:
    """Formats the answer into a structured markdown report with REAL timing."""
    question = state.get("question", "")
    answer = state.get("answer", "No answer generated.")
    route = state.get("route", "unknown")
    grade_reasoning = state.get("grade_reasoning", "")
    graded_docs = state.get("graded_docs", [])
    total_calls = state.get("total_llm_calls", 0)

    t0 = time.time()

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

    latency_ms = round((time.time() - t0) * 1000, 2)

    print(f"[Formatter] Generated report ({len(report)} chars)")

    # ── Build REAL trace entry ──
    trace_entry = {
        "node_name": "Format Report",
        "run_type": "chain",
        "latency_ms": latency_ms,
        "inputs": {"question": question, "answer_length": len(answer), "docs_count": len(graded_docs)},
        "outputs": {"report_length": len(report)},
        "error": None,
        "tags": ["formatter", "output"],
        "ls_metadata": {
            "output_format": "markdown",
        },
        "status": "success",
    }

    return {
        "final_report": report,
        "node_traces": _append_trace(state, trace_entry),
    }
