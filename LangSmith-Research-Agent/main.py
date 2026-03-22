"""
AI Research Agent — Main Entry Point

Demonstrates comprehensive LangSmith setup:
1. Environment configuration (LANGSMITH_TRACING, LANGSMITH_PROJECT)
2. Thread tracking for multi-turn conversations
3. Feedback collection after execution
4. Trace flushing before exit
5. Selective tracing via tracing_context
6. Dynamic project routing
7. Local file logging of all trace data
"""

import os
import json
import argparse
import uuid
from datetime import datetime
from dotenv import load_dotenv


def setup_langsmith():
    """Configure LangSmith environment variables for tracing."""
    # Core tracing setup
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ.setdefault("LANGSMITH_PROJECT", "langsmith-research-agent")
    
    # Verify API key
    if not os.getenv("LANGSMITH_API_KEY"):
        print("\n⚠️  WARNING: LANGSMITH_API_KEY not set in .env")
        print("   Traces will NOT be sent to LangSmith.")
        print("   Get a free key at: https://smith.langchain.com\n")
        os.environ["LANGSMITH_TRACING"] = "false"
    else:
        print(f"✅ LangSmith tracing enabled → project: {os.environ['LANGSMITH_PROJECT']}")


def run_research(question: str, thread_id: str = None, project_name: str = None, log_file: str = None):
    """
    Run a single research query through the agent.
    
    Demonstrates:
    - Thread ID generation for conversation tracking
    - Dynamic project routing via tracing_context
    - Feedback run ID capture for async feedback
    - Local file logging of trace data (when log_file is specified)
    - LangSmith API logging (cloud-sourced trace reports)
    """
    import langsmith as ls
    from langsmith import traceable
    from src.graph import build_graph

    # Generate thread ID if not provided (for multi-turn tracking)
    if not thread_id:
        thread_id = f"research-{uuid.uuid4().hex[:8]}"

    # ── LangSmith: Local file logging ──
    # When a log_file path is specified, all trace data is also
    # written to a local .jsonl file for offline analysis.
    local_logger = None
    if log_file:
        from src.local_logger import LocalFileLogger
        local_logger = LocalFileLogger(log_file)

    print(f"\n{'='*60}")
    print(f"🔍 Research Agent")
    print(f"   Question: {question}")
    print(f"   Thread:   {thread_id}")
    if local_logger:
        print(f"   Log file: {log_file}")
    print(f"{'='*60}\n")

    graph = build_graph()

    # Prepare the input state
    input_state = {
        "question": question,
        "thread_id": thread_id,
        "total_llm_calls": 0,
    }

    # ── Wrap graph.invoke with @traceable to capture the LangSmith trace ID ──
    @traceable(name="ResearchAgent", run_type="chain")
    def _run_graph(input_state: dict) -> dict:
        return graph.invoke(input_state)

    langsmith_trace_id = None  # Will be captured after invocation

    # ── LangSmith: Dynamic project routing ──
    # You can send traces to different projects based on context
    if project_name:
        with ls.tracing_context(project_name=project_name):
            result = _run_graph(input_state)
    else:
        result = _run_graph(input_state)

    # Capture the LangSmith trace ID from the @traceable wrapper
    try:
        run_tree = ls.get_current_run_tree()
        if run_tree:
            langsmith_trace_id = str(run_tree.trace_id)
    except Exception:
        pass

    # Display results
    report = result.get("final_report", "No report generated.")
    feedback_run_id = result.get("feedback_run_id", "")
    total_calls = result.get("total_llm_calls", 0)

    # ── Local logging: Write trace summary to file ──
    if local_logger:
        _log_pipeline_results(local_logger, result, question, thread_id, project_name)
        local_logger.write_markdown_report(question=question, thread_id=thread_id)
        print(f"\n{local_logger.get_summary()}")

    print(f"\n{'='*60}")
    print(report)
    print(f"\n{'='*60}")
    print(f"📊 Total LLM calls: {total_calls}")
    print(f"🧵 Thread ID: {thread_id}")
    if feedback_run_id:
        print(f"📝 Feedback Run ID: {feedback_run_id}")

    # ── LangSmith API Logging (cloud-sourced) ──
    # Fetches the trace from LangSmith's cloud API and generates
    # a separate report. Runs ALONGSIDE (not instead of) local logging.
    if os.getenv("LANGSMITH_TRACING") == "true":
        try:
            from src.langsmith_api_logger import LangSmithAPILogger
            api_logger = LangSmithAPILogger(output_dir=os.path.dirname(log_file) if log_file else "logs")

            # If we captured a trace_id from the @traceable wrapper, use it.
            # Otherwise, fall back to fetching the most recent trace.
            if langsmith_trace_id:
                api_logger.fetch_and_log(
                    trace_id=langsmith_trace_id,
                    question=question,
                    thread_id=thread_id,
                )
            else:
                # Fall back: fetch the most recent root run from the project
                from langsmith import Client
                client = Client()
                proj = project_name or os.environ.get("LANGSMITH_PROJECT", "langsmith-research-agent")
                recent_runs = list(client.list_runs(
                    project_name=proj,
                    is_root=True,
                    limit=1,
                ))
                if recent_runs:
                    api_logger.fetch_and_log(
                        trace_id=str(recent_runs[0].trace_id),
                        question=question,
                        thread_id=thread_id,
                    )
        except Exception as e:
            print(f"⚠️  [LangSmith API Logger] Skipped: {e}")

    return result, thread_id, feedback_run_id


def _log_pipeline_results(logger, result: dict, question: str, thread_id: str,
                          project_name: str = None):
    """
    Log pipeline results using REAL instrumentation data from node_traces.

    Instead of reconstructing/estimating data after the fact, this reads
    the actual trace entries that each node captured during execution:
    real timing, real token counts, real prompts, and real completions.
    """
    import sys
    import platform
    from datetime import datetime, timezone

    trace_id = f"trace-{uuid.uuid4().hex[:12]}"
    logger._trace_id = trace_id
    proj = project_name or os.environ.get("LANGSMITH_PROJECT", "langsmith-research-agent")

    # Gemini 2.5 Flash pricing (per token)
    INPUT_PRICE = 0.00000015   # $0.15 per 1M input tokens
    OUTPUT_PRICE = 0.0000006   # $0.60 per 1M output tokens

    node_traces = result.get("node_traces", []) or []

    for trace_entry in node_traces:
        # Calculate cost from REAL token counts
        usage = trace_entry.get("usage_metadata") or {}
        input_tok = usage.get("input_tokens") or 0
        output_tok = usage.get("output_tokens") or 0
        cost = (input_tok * INPUT_PRICE + output_tok * OUTPUT_PRICE) if (input_tok or output_tok) else None

        logger.log_run({
            "id": f"run-{uuid.uuid4().hex[:8]}",
            "trace_id": trace_id,
            "parent_run_id": trace_id,
            "name": trace_entry.get("node_name", "Unknown"),
            "run_type": trace_entry.get("run_type", "chain"),
            "status": trace_entry.get("status", "success"),
            "error": trace_entry.get("error"),
            "latency_ms": trace_entry.get("latency_ms"),
            "inputs": trace_entry.get("inputs"),
            "outputs": trace_entry.get("outputs"),
            # LLM-specific (real data from AIMessage)
            "llm_prompts": trace_entry.get("messages_sent"),
            "llm_completion": trace_entry.get("completion"),
            "usage_metadata": usage if usage else None,
            "estimated_cost_usd": cost,
            "response_metadata": trace_entry.get("response_metadata"),
            "finish_reason": trace_entry.get("finish_reason"),
            # Retriever-specific
            "retrieved_documents": trace_entry.get("retrieved_documents"),
            # LangSmith ls_ metadata params
            "metadata": trace_entry.get("ls_metadata", {}),
            "tags": trace_entry.get("tags", []),
            "thread_id": thread_id,
            "project_name": proj,
        })

    # Environment info (captured once)
    env_info = {
        "python_version": sys.version.split()[0],
        "os": platform.system(),
        "machine": platform.machine(),
        "platform": platform.platform(),
    }
    logger._env_info = env_info


def submit_feedback(run_id: str, score: float, comment: str = ""):
    """
    Submit feedback to LangSmith for a specific run.
    
    Demonstrates:
    - Programmatic feedback collection
    - Associating user scores with specific runs
    """
    if not os.getenv("LANGSMITH_API_KEY"):
        print("⚠️  Cannot submit feedback: LANGSMITH_API_KEY not set")
        return

    from langsmith import Client
    
    client = Client()
    client.create_feedback(
        run_id,
        key="user-rating",
        score=score,
        comment=comment or f"User rated this response {score}/1.0",
    )
    print(f"✅ Feedback submitted: score={score}, run_id={run_id[:16]}...")


def main():
    """Main entry point with CLI argument parsing."""
    # Load .env from the parent Projects directory (shared with Gen AI News Agent)
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✅ Loaded .env from: {env_path}")
    else:
        load_dotenv()
        print("📁 Using default .env location")

    # Suppress Pydantic warnings from LangChain-Google
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

    # Set up LangSmith
    setup_langsmith()

    # Parse CLI arguments
    parser = argparse.ArgumentParser(
        description="AI Research Agent with LangSmith Observability"
    )
    parser.add_argument(
        "--question", "-q",
        type=str,
        default="What is LangGraph and how does it work?",
        help="Research question to investigate",
    )
    parser.add_argument(
        "--thread-id", "-t",
        type=str,
        default=None,
        help="Thread ID for conversation tracking (auto-generated if omitted)",
    )
    parser.add_argument(
        "--project", "-p",
        type=str,
        default=None,
        help="LangSmith project name (overrides default)",
    )
    parser.add_argument(
        "--feedback",
        type=float,
        default=None,
        help="Submit feedback score (0.0-1.0) after execution",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Save report to this file path",
    )
    parser.add_argument(
        "--log-file", "-l",
        type=str,
        default=None,
        help="Path to write local trace logs in JSONL format (e.g., logs/traces.jsonl)",
    )
    args = parser.parse_args()

    # Run the research agent
    result, thread_id, feedback_run_id = run_research(
        question=args.question,
        thread_id=args.thread_id,
        project_name=args.project,
        log_file=args.log_file,
    )

    # Submit feedback if requested
    if args.feedback is not None and feedback_run_id:
        submit_feedback(feedback_run_id, args.feedback)

    # Save report if output path specified
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result.get("final_report", ""))
        print(f"\n📄 Report saved to: {args.output}")

    # ── LangSmith: Ensure all traces are flushed ──
    # Critical for serverless environments or scripts that exit quickly
    try:
        from langchain_core.tracers.langchain import wait_for_all_tracers
        wait_for_all_tracers()
        print("✅ All traces flushed to LangSmith")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
