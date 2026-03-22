"""
AI Research Agent — Interactive Demo Runner

A guided script that demonstrates ALL LangSmith features in action:
1. Basic tracing (single question)
2. Thread tracking (follow-up question)
3. Feedback submission
4. Trace querying
5. Selective tracing
6. Dynamic project routing
7. Local file logging

Designed with generous delays to avoid Gemini free-tier rate limits.
"""

import os
import time
import uuid
from dotenv import load_dotenv


def pause(seconds: float, message: str = ""):
    """Rate-limit friendly pause with optional message."""
    if message:
        print(f"\n⏳ {message} ({seconds}s delay for rate limits)...")
    time.sleep(seconds)


def demo_1_basic_tracing():
    """
    Demo 1: Basic Tracing
    
    Shows: auto-tracing of the full LangGraph pipeline with nested runs.
    After this runs, check LangSmith UI to see:
    - Full trace tree with all 6 nodes
    - Conditional routing (which path was taken)
    - LLM calls with model info and token counts
    - Tool and retriever runs with special rendering
    """
    from main import run_research
    
    print("\n" + "="*60)
    print("📌 DEMO 1: Basic Tracing")
    print("="*60)
    print("""
    This demo runs a single question through the research agent.
    
    ✅ LangSmith features demonstrated:
       • Auto-tracing of LangGraph pipeline
       • @traceable decorator with metadata & tags
       • run_type variants: llm, tool, retriever
       • ls_provider + ls_model_name for model identification
       • Manual token tracking via get_current_run_tree()
       • Cost tracking on tool runs
       • Retriever document rendering
    """)

    result, thread_id, run_id = run_research(
        question="What are the key differences between LangChain and LangGraph?"
    )
    
    return thread_id, run_id


def demo_2_thread_tracking(thread_id: str):
    """
    Demo 2: Thread Tracking (Multi-Turn Conversations)
    
    Shows: using the same thread_id to link multiple traces into a conversation.
    After this runs, check LangSmith UI → Threads tab to see both
    questions grouped under the same thread.
    """
    from main import run_research
    
    print("\n" + "="*60)
    print("📌 DEMO 2: Thread Tracking (Multi-Turn)")
    print("="*60)
    print(f"""
    This demo asks a follow-up question using the same thread_id.
    Thread ID: {thread_id}
    
    ✅ LangSmith features demonstrated:
       • Thread metadata (thread_id) for conversation grouping
       • Multi-turn conversation tracking in LangSmith UI
       • Thread-level feedback aggregation
    """)

    result, _, run_id = run_research(
        question="How does LangGraph handle state persistence?",
        thread_id=thread_id,
    )
    
    return run_id


def demo_3_feedback(run_id: str):
    """
    Demo 3: Feedback Collection
    
    Shows: submitting user feedback scores to LangSmith.
    After this runs, check the trace in LangSmith UI to see
    the feedback score attached to the run.
    """
    from main import submit_feedback
    
    print("\n" + "="*60)
    print("📌 DEMO 3: Feedback Collection")
    print("="*60)
    print(f"""
    This demo submits feedback for the previous answer.
    Run ID: {run_id}
    
    ✅ LangSmith features demonstrated:
       • Programmatic feedback via Client.create_feedback()
       • Feedback scores attached to specific runs
       • Feedback visible in LangSmith trace view
    """)

    if run_id and os.getenv("LANGSMITH_API_KEY"):
        submit_feedback(run_id, score=0.9, comment="Good research answer, comprehensive and accurate")
        print("✅ Feedback submitted successfully!")
    else:
        print("⚠️  Skipped: No run_id or LANGSMITH_API_KEY not set")


def demo_4_trace_querying():
    """
    Demo 4: Trace Querying
    
    Shows: how to programmatically query traces from LangSmith.
    """
    print("\n" + "="*60)
    print("📌 DEMO 4: Trace Querying")
    print("="*60)
    print("""
    ✅ LangSmith features demonstrated:
       • Programmatic trace querying via Client.list_runs()
       • Filtering by metadata, tags, and run type
       • Trace analysis and aggregation
    """)

    if not os.getenv("LANGSMITH_API_KEY"):
        print("⚠️  Skipped: LANGSMITH_API_KEY not set")
        return

    from langsmith import Client
    client = Client()
    project_name = os.environ.get("LANGSMITH_PROJECT", "langsmith-research-agent")

    try:
        # Query recent runs
        print(f"\n📊 Querying traces from project: {project_name}")
        
        runs = list(client.list_runs(
            project_name=project_name,
            limit=5,
        ))
        
        print(f"\n   Found {len(runs)} recent runs:")
        for run in runs:
            duration = ""
            if run.end_time and run.start_time:
                duration = f" ({(run.end_time - run.start_time).total_seconds():.1f}s)"
            print(f"   • {run.name} [{run.run_type}]{duration}")
            if run.tags:
                print(f"     Tags: {', '.join(run.tags)}")

    except Exception as e:
        print(f"   Error querying traces: {e}")


def demo_5_selective_tracing():
    """
    Demo 5: Selective Tracing
    
    Shows: how to enable/disable tracing for specific calls.
    """
    import langsmith as ls
    from main import run_research

    print("\n" + "="*60)
    print("📌 DEMO 5: Selective Tracing")  
    print("="*60)
    print("""
    ✅ LangSmith features demonstrated:
       • tracing_context(enabled=False) to skip tracing
       • tracing_context(enabled=True) for explicit opt-in
       • Useful for dev/test vs production tracing
    """)

    # This call will NOT be traced
    print("\n   Running with tracing DISABLED (won't appear in LangSmith)...")
    with ls.tracing_context(enabled=False):
        result, _, _ = run_research(
            question="What is machine learning?",
        )
    print("   ✅ Completed without tracing")


def demo_6_dynamic_routing():
    """
    Demo 6: Dynamic Project Routing
    
    Shows: sending traces to different LangSmith projects.
    """
    from main import run_research

    print("\n" + "="*60)
    print("📌 DEMO 6: Dynamic Project Routing")
    print("="*60)
    print("""
    ✅ LangSmith features demonstrated:
       • Dynamic project routing via tracing_context(project_name=...)
       • Sending experiment traces to separate projects
       • Production vs staging trace separation
    """)

    result, _, _ = run_research(
        question="Explain the concept of AI agents",
        project_name="research-agent-experiments",
    )
    print("   ✅ Trace sent to project: 'research-agent-experiments'")


def demo_7_local_logging():
    """
    Demo 7: Local File Logging
    
    Shows: writing all LangSmith trace data to a local JSONL file.
    After this runs, the file logs/demo_trace.jsonl will contain
    a structured record for every node in the pipeline.
    """
    from main import run_research

    print("\n" + "="*60)
    print("📌 DEMO 7: Local File Logging")
    print("="*60)
    print("""
    This demo runs a question with local JSONL logging enabled.
    All trace data (inputs, outputs, metadata, tokens) is written
    to a local file alongside being sent to LangSmith cloud.
    
    ✅ LangSmith features demonstrated:
       • Local file logging of trace data
       • JSONL format (one JSON object per line)
       • Structured records for every pipeline stage
       • Offline analysis without the LangSmith UI
    """)

    log_file = "logs/demo_trace.jsonl"
    result, _, _ = run_research(
        question="What is retrieval augmented generation and why is it useful?",
        log_file=log_file,
    )

    # Read back and display the logged entries
    print(f"\n   📂 Log file contents ({log_file}):")
    try:
        from src.local_logger import LocalFileLogger
        logger = LocalFileLogger.__new__(LocalFileLogger)
        logger.log_path = log_file
        logger.print_summary_table()
    except Exception as e:
        print(f"   Error reading log: {e}")


def main():
    """Run the full demo suite with rate-limit-friendly delays."""
    # Load env
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        load_dotenv()

    # Suppress warnings
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

    # Setup LangSmith
    from main import setup_langsmith
    setup_langsmith()

    print("\n" + "🚀"*20)
    print("\n  AI Research Agent — LangSmith Feature Demo")
    print("  This demo showcases ALL LangSmith observability features")
    print("  with rate-limit-friendly delays between operations.\n")
    print("🚀"*20)

    # Demo 1: Basic Tracing
    thread_id, run_id_1 = demo_1_basic_tracing()
    pause(8, "Waiting between demos to respect Gemini rate limits")

    # Demo 2: Thread Tracking (reuses thread_id from Demo 1)
    run_id_2 = demo_2_thread_tracking(thread_id)
    pause(3, "Brief pause before feedback")

    # Demo 3: Feedback Collection
    demo_3_feedback(run_id_2)
    pause(3, "Brief pause before querying")

    # Demo 4: Trace Querying
    demo_4_trace_querying()
    pause(8, "Waiting between demos to respect Gemini rate limits")

    # Demo 5: Selective Tracing
    demo_5_selective_tracing()
    pause(8, "Waiting between demos to respect Gemini rate limits")

    # Demo 6: Dynamic Project Routing
    demo_6_dynamic_routing()
    pause(8, "Waiting between demos to respect Gemini rate limits")

    # Demo 7: Local File Logging
    demo_7_local_logging()

    # Flush all traces
    try:
        from langchain_core.tracers.langchain import wait_for_all_tracers
        wait_for_all_tracers()
    except ImportError:
        pass

    print("\n" + "="*60)
    print("🎉 ALL DEMOS COMPLETE!")
    print("="*60)
    print("""
    Check your LangSmith dashboard at: https://smith.langchain.com
    
    What to verify:
    ┌─────────────────────────────────────────────────────────────┐
    │  Project: langsmith-research-agent                         │
    │                                                            │
    │  ✅ Traces tab:                                            │
    │     • Nested trace trees (router → search/retriever →      │
    │       grader → answer → formatter)                         │
    │     • LLM runs show model info + estimated token counts    │
    │     • Tool runs show cost metadata                         │
    │     • Retriever runs show documents in rich format         │
    │     • Tags and metadata visible on each run                │
    │                                                            │
    │  ✅ Threads tab:                                           │
    │     • Both Demo 1 & 2 grouped under same thread            │
    │     • Thread shows conversation flow                       │
    │                                                            │
    │  ✅ Feedback:                                              │
    │     • User rating visible on Demo 2's answer run           │
    │                                                            │
    │  ✅ Projects:                                              │
    │     • 'research-agent-experiments' has Demo 6's trace      │
    │                                                            │
    │  ✅ Local log file:                                        │
    │     • logs/demo_trace.jsonl created with 6 entries per run │
    │     • Each line has: name, run_type, inputs, outputs,      │
    │       metadata, tags, tokens, latency                      │
    │                                                            │
    │  ❌ Not traced:                                            │
    │     • Demo 5 (selective tracing disabled)                  │
    └─────────────────────────────────────────────────────────────┘
    
    Total Gemini API calls: ~15 (5 demos × 3 calls each)
    Estimated time: ~4-5 minutes (with rate limit delays)
    """)


if __name__ == "__main__":
    main()
