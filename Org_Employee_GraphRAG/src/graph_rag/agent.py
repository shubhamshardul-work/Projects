"""
LangGraph Agent — multi-node graph for natural language → Cypher → answer.

Nodes:
  1. planner      – Analyse intent & extract entities
  2. cypher_gen   – Generate Cypher query
  3. executor     – Run Cypher on Neo4j
  4. synthesizer  – Format results into natural language
"""
from __future__ import annotations

import re
import json
from typing import Any, Dict, List, TypedDict, Annotated

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from src.llm_factory import get_llm
from src.neo4j_manager import Neo4jManager
from src.graph_rag.prompts import (
    CYPHER_GENERATION_PROMPT,
    SYNTHESIZER_PROMPT,
    PLANNER_PROMPT,
)
from src.utils.logger import log


# ───────────────────────────────────────────────────────────────────────
# State
# ───────────────────────────────────────────────────────────────────────

class GraphRAGState(TypedDict):
    """State flowing through the LangGraph."""
    question: str
    plan: str
    cypher: str
    results: List[Dict[str, Any]]
    answer: str
    error: str
    retry_count: int


# ───────────────────────────────────────────────────────────────────────
# Agent Builder
# ───────────────────────────────────────────────────────────────────────

class GraphRAGAgent:
    """Builds and exposes the LangGraph agent."""

    MAX_RETRIES = 2

    def __init__(self, neo4j_manager: Neo4jManager, llm_provider: str | None = None):
        self.db = neo4j_manager
        self.llm = get_llm(provider=llm_provider)
        self.graph = self._build_graph()

    # ── Node implementations ─────────────────────────────────────────

    def _planner_node(self, state: GraphRAGState) -> dict:
        """Analyse the user question and create a query plan."""
        log.info("[bold cyan]🧠 Planner[/] Analysing question …")
        prompt = PLANNER_PROMPT.format(question=state["question"])
        response = self.llm.invoke([
            SystemMessage(content="You are an expert query planner for an organizational knowledge graph."),
            HumanMessage(content=prompt),
        ])
        plan = response.content.strip()
        log.info(f"[bold cyan]🧠 Planner[/] Plan ready ({len(plan)} chars)")
        return {"plan": plan}

    def _cypher_gen_node(self, state: GraphRAGState) -> dict:
        """Generate a Cypher query from the plan + question."""
        log.info("[bold yellow]⚡ Cypher Gen[/] Generating query …")

        error_context = ""
        if state.get("error"):
            error_context = (
                f"\n\nPREVIOUS ATTEMPT FAILED with error:\n{state['error']}\n"
                f"Previous Cypher:\n{state.get('cypher', '')}\n"
                "Please fix the query and try again."
            )

        prompt = CYPHER_GENERATION_PROMPT.replace(
            "{question}", state["question"]
        ) + error_context

        if state.get("plan"):
            prompt += f"\n\nQuery Plan:\n{state['plan']}"

        response = self.llm.invoke([
            SystemMessage(content="You are an expert Neo4j Cypher query generator. Return ONLY the Cypher query."),
            HumanMessage(content=prompt),
        ])

        raw = response.content.strip()

        # Extract cypher from markdown code blocks if present
        cypher = self._extract_cypher(raw)
        log.info(f"[bold yellow]⚡ Cypher Gen[/]\n{cypher}")
        return {"cypher": cypher, "error": ""}

    def _executor_node(self, state: GraphRAGState) -> dict:
        """Execute the Cypher query against Neo4j."""
        log.info("[bold green]🔧 Executor[/] Running query …")
        cypher = state["cypher"]

        if cypher.startswith("// CANNOT_ANSWER"):
            reason = cypher.replace("// CANNOT_ANSWER:", "").strip()
            log.info(f"[bold green]🔧 Executor[/] Query cannot be answered: {reason}")
            return {
                "results": [],
                "error": "",
                "answer": f"I'm sorry, I cannot answer this question with the available data. Reason: {reason}",
            }

        try:
            results = self.db.run_query(cypher)
            log.info(f"[bold green]🔧 Executor[/] Got {len(results)} results")
            return {
                "results": results,
                "error": "",
                "retry_count": state.get("retry_count", 0),
            }
        except Exception as e:
            error_msg = str(e)
            log.error(f"[bold red]🔧 Executor[/] Error: {error_msg}")
            retry = state.get("retry_count", 0) + 1
            return {
                "results": [],
                "error": error_msg,
                "retry_count": retry,
            }

    def _synthesizer_node(self, state: GraphRAGState) -> dict:
        """Format graph results into a natural language answer."""
        log.info("[bold magenta]📝 Synthesizer[/] Formatting response …")

        # If we already have an answer (from CANNOT_ANSWER), pass through
        if state.get("answer"):
            return {"answer": state["answer"]}

        results = state.get("results", [])

        # Truncate large results for LLM context
        results_text = json.dumps(results[:50], indent=2, default=str)
        if len(results) > 50:
            results_text += f"\n... and {len(results) - 50} more results"

        prompt = SYNTHESIZER_PROMPT.format(
            question=state["question"],
            cypher=state["cypher"],
            results=results_text,
        )

        response = self.llm.invoke([
            SystemMessage(content="You are a helpful HR analytics assistant. Format your response clearly with tables and bullet points where appropriate."),
            HumanMessage(content=prompt),
        ])

        answer = response.content.strip()
        log.info(f"[bold magenta]📝 Synthesizer[/] Response ready ({len(answer)} chars)")
        return {"answer": answer}

    # ── Routing ───────────────────────────────────────────────────────

    def _should_retry(self, state: GraphRAGState) -> str:
        """Decide whether to retry Cypher generation or proceed."""
        if state.get("error") and state.get("retry_count", 0) < self.MAX_RETRIES:
            log.info(f"[bold yellow]🔄 Retrying[/] (attempt {state['retry_count']})")
            return "retry"
        if state.get("error"):
            # Max retries exceeded — let synthesizer handle the error
            return "give_up"
        return "success"

    # ── Graph construction ────────────────────────────────────────────

    def _build_graph(self) -> StateGraph:
        """Wire up the LangGraph state machine."""
        builder = StateGraph(GraphRAGState)

        # Add nodes
        builder.add_node("planner", self._planner_node)
        builder.add_node("cypher_gen", self._cypher_gen_node)
        builder.add_node("executor", self._executor_node)
        builder.add_node("synthesizer", self._synthesizer_node)

        # Set entry point
        builder.set_entry_point("planner")

        # Edges
        builder.add_edge("planner", "cypher_gen")
        builder.add_edge("cypher_gen", "executor")

        # Conditional edge after executor
        builder.add_conditional_edges(
            "executor",
            self._should_retry,
            {
                "retry": "cypher_gen",
                "success": "synthesizer",
                "give_up": "synthesizer",
            },
        )

        builder.add_edge("synthesizer", END)

        return builder.compile()

    # ── Public API ────────────────────────────────────────────────────

    def query(self, question: str) -> Dict[str, Any]:
        """
        Run a natural language query through the GraphRAG pipeline.

        Returns dict with keys: answer, cypher, results, error
        """
        log.info(f"\n[bold white on blue] QUERY [/] {question}\n")

        initial_state: GraphRAGState = {
            "question": question,
            "plan": "",
            "cypher": "",
            "results": [],
            "answer": "",
            "error": "",
            "retry_count": 0,
        }

        final_state = self.graph.invoke(initial_state)

        return {
            "answer": final_state.get("answer", "Sorry, I could not process your query."),
            "cypher": final_state.get("cypher", ""),
            "results": final_state.get("results", []),
            "error": final_state.get("error", ""),
        }

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_cypher(text: str) -> str:
        """Extract Cypher from potential markdown code blocks."""
        # Try to extract from ```cypher ... ``` or ``` ... ```
        patterns = [
            r"```cypher\s*\n(.*?)```",
            r"```\s*\n(.*?)```",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
        # If no code block, return as-is
        return text.strip()
