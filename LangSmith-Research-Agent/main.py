"""
AI Research Agent — Main Entry Point

Demonstrates comprehensive LangSmith setup:
1. Environment configuration (LANGSMITH_TRACING, LANGSMITH_PROJECT)
2. Thread tracking for multi-turn conversations
3. Feedback collection after execution
4. Trace flushing before exit
5. Selective tracing via tracing_context
6. Dynamic project routing
"""

import os
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


def run_research(question: str, thread_id: str = None, project_name: str = None):
    """
    Run a single research query through the agent.
    
    Demonstrates:
    - Thread ID generation for conversation tracking
    - Dynamic project routing via tracing_context
    - Feedback run ID capture for async feedback
    """
    import langsmith as ls
    from src.graph import build_graph

    # Generate thread ID if not provided (for multi-turn tracking)
    if not thread_id:
        thread_id = f"research-{uuid.uuid4().hex[:8]}"

    print(f"\n{'='*60}")
    print(f"🔍 Research Agent")
    print(f"   Question: {question}")
    print(f"   Thread:   {thread_id}")
    print(f"{'='*60}\n")

    graph = build_graph()

    # ── LangSmith: Dynamic project routing ──
    # You can send traces to different projects based on context
    if project_name:
        with ls.tracing_context(project_name=project_name):
            result = graph.invoke({
                "question": question,
                "thread_id": thread_id,
                "total_llm_calls": 0,
            })
    else:
        result = graph.invoke({
            "question": question,
            "thread_id": thread_id,
            "total_llm_calls": 0,
        })

    # Display results
    report = result.get("final_report", "No report generated.")
    feedback_run_id = result.get("feedback_run_id", "")
    total_calls = result.get("total_llm_calls", 0)

    print(f"\n{'='*60}")
    print(report)
    print(f"\n{'='*60}")
    print(f"📊 Total LLM calls: {total_calls}")
    print(f"🧵 Thread ID: {thread_id}")
    if feedback_run_id:
        print(f"📝 Feedback Run ID: {feedback_run_id}")

    return result, thread_id, feedback_run_id


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
    args = parser.parse_args()

    # Run the research agent
    result, thread_id, feedback_run_id = run_research(
        question=args.question,
        thread_id=args.thread_id,
        project_name=args.project,
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
