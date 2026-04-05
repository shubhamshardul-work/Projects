"""
Dynamic Few-Shot Generator — generates Cypher query examples
from the live Neo4j schema at runtime.

Replaces the hardcoded cypher_templates.py.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from src.neo4j_manager import Neo4jManager
from src.utils.logger import log


def generate_few_shots(
    db: Neo4jManager,
    schema_text: str,
    llm,
    num_examples: int = 6,
) -> str:
    """
    Use the LLM to generate few-shot Cypher examples based on the live schema.

    Args:
        db:          Connected Neo4jManager
        schema_text: Schema text from dynamic_schema.get_schema_for_cypher()
        llm:         LangChain ChatModel
        num_examples: Number of examples to generate

    Returns:
        Formatted few-shot text for prompt injection.
    """
    log.info("[bold cyan]Few-Shot Generator[/] Generating examples from live schema …")

    # Sample some actual data from the graph
    samples = _sample_graph_data(db)

    prompt = f"""You are a Neo4j Cypher expert. Given the following graph schema, 
generate {num_examples} diverse example queries that a user might ask about this data.

GRAPH SCHEMA:
{schema_text}

SAMPLE DATA FROM THE GRAPH:
{samples}

REQUIREMENTS:
1. Cover different query patterns: simple lookups, multi-hop traversals, aggregations, filtering
2. Use realistic questions a business user would ask
3. Each query must be valid Cypher that would run against this schema
4. Use DISTINCT where appropriate to avoid duplicates
5. Include WHERE filters, ORDER BY, and LIMIT where appropriate
6. Use meaningful column aliases with AS

Return ONLY a JSON array of objects, each with "question" and "cypher" keys.
No markdown, no explanations, just the JSON array.
"""

    response = llm.invoke([
        SystemMessage(content="You are a Neo4j Cypher expert. Return ONLY a valid JSON array."),
        HumanMessage(content=prompt),
    ])

    raw = response.content.strip()

    # Parse the examples
    try:
        examples = _parse_examples(raw)
    except Exception as e:
        log.warning(f"[bold yellow]Few-Shot Generator[/] Parse error: {e}. Using fallback.")
        examples = _generate_fallback_examples(schema_text)

    # Format as text
    few_shot_text = _format_examples(examples)
    log.info(f"[bold cyan]Few-Shot Generator[/] ✅ Generated {len(examples)} examples")
    return few_shot_text


def _sample_graph_data(db: Neo4jManager) -> str:
    """Sample a few values from each node type in the graph."""
    lines = []
    try:
        # Get all node labels
        labels_result = db.run_query("CALL db.labels() YIELD label RETURN label")
        labels = [r["label"] for r in labels_result]

        for label in labels[:10]:  # Limit to 10 node types
            try:
                sample = db.run_query(f"""
                    MATCH (n:{label})
                    RETURN n LIMIT 2
                """)
                if sample:
                    props = dict(sample[0]["n"])
                    # Truncate large values
                    clean = {k: str(v)[:80] for k, v in list(props.items())[:8]}
                    lines.append(f"{label} sample: {json.dumps(clean, default=str)}")
            except Exception:
                continue
    except Exception:
        lines.append("(Could not sample data)")

    return "\n".join(lines) if lines else "(Empty graph)"


def _parse_examples(raw: str) -> List[Dict[str, str]]:
    """Parse LLM response as a JSON array of {question, cypher}."""
    # Strip markdown code fences
    if "```" in raw:
        raw = re.sub(r"```(?:json)?\s*\n?", "", raw)
        raw = raw.strip()

    examples = json.loads(raw)

    if not isinstance(examples, list):
        raise ValueError("Expected a JSON array")

    return [{"question": ex["question"], "cypher": ex["cypher"]} for ex in examples]


def _generate_fallback_examples(schema_text: str) -> List[Dict[str, str]]:
    """Generate basic structural examples without LLM."""
    return [
        {
            "question": "Show all node types and counts",
            "cypher": "MATCH (n) RETURN labels(n)[0] AS type, count(n) AS count ORDER BY count DESC",
        },
        {
            "question": "Show all relationship types and counts",
            "cypher": "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY count DESC",
        },
    ]


def _format_examples(examples: List[Dict[str, str]]) -> str:
    """Format examples as text for prompt injection."""
    lines = []
    for i, ex in enumerate(examples, 1):
        lines.append(f"Example {i}:")
        lines.append(f"Question: {ex['question']}")
        lines.append(f"Cypher:\n{ex['cypher']}")
        lines.append("")
    return "\n".join(lines)
