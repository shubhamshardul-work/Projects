"""
Local file logger for LangSmith traces.

Produces TWO output files:
1. .jsonl — Machine-readable JSON Lines (for programmatic analysis)
2. .md   — Human-readable Markdown trace report (for visual inspection)

The Markdown file mirrors what you'd see in the LangSmith UI:
trace tree, LLM prompts/completions, token counts, latency,
retrieved documents, costs, metadata, tags, and feedback.

All data is REAL — captured during actual execution, not estimated.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional


class LocalFileLogger:
    """
    Writes LangSmith-style trace data to local files.

    Produces:
    - A `.jsonl` file (one JSON object per run for programmatic use)
    - A `.md` file (human-readable Markdown trace report)
    """

    def __init__(self, log_path: str = "logs/langsmith_traces.jsonl"):
        self.jsonl_path = log_path
        self.md_path = log_path.rsplit(".", 1)[0] + ".md"
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        self._run_count = 0
        self._runs: list[dict] = []   # Buffer for Markdown generation
        self._trace_id = ""
        self._session_start = datetime.now(timezone.utc)
        self._env_info: dict = {}
        self._feedback: list[dict] = []
        print(f"📝 [LocalFileLogger] Logging to:")
        print(f"   JSONL → {os.path.abspath(self.jsonl_path)}")
        print(f"   MD   → {os.path.abspath(self.md_path)}")

    # ─── Serialization ────────────────────────────────────────────────────

    def _safe(self, obj: Any) -> Any:
        """Make an object JSON-serializable."""
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: self._safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._safe(item) for item in obj]
        return str(obj)

    # ─── Core Logging ─────────────────────────────────────────────────────

    def log_run(self, run: dict) -> None:
        """Write a single run to the JSONL file and buffer it for Markdown."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": run.get("trace_id", self._trace_id),
            "run_id": run.get("id", ""),
            "parent_run_id": run.get("parent_run_id", ""),
            "name": run.get("name", ""),
            "run_type": run.get("run_type", ""),
            "status": run.get("status", "success"),
            "error": run.get("error"),
            # ── Timing ──
            "start_time": self._safe(run.get("start_time")),
            "end_time": self._safe(run.get("end_time")),
            "latency_ms": run.get("latency_ms"),
            # ── I/O ──
            "inputs": self._safe(run.get("inputs")),
            "outputs": self._safe(run.get("outputs")),
            # ── LLM-specific ──
            "llm_prompts": self._safe(run.get("llm_prompts")),
            "llm_completion": run.get("llm_completion"),
            "llm_config": self._safe(run.get("llm_config")),
            # ── Tokens & Cost ──
            "usage_metadata": self._safe(run.get("usage_metadata")),
            "estimated_cost_usd": run.get("estimated_cost_usd"),
            # ── Response Metadata (finish_reason, safety_ratings, model) ──
            "response_metadata": self._safe(run.get("response_metadata")),
            "finish_reason": run.get("finish_reason"),
            # ── Retriever-specific ──
            "retrieved_documents": self._safe(run.get("retrieved_documents")),
            # ── Classification ──
            "metadata": self._safe(run.get("metadata")),
            "tags": run.get("tags", []),
            # ── Thread & Feedback ──
            "thread_id": run.get("thread_id", ""),
            "feedback": self._safe(run.get("feedback")),
            # ── Project ──
            "project_name": run.get("project_name", ""),
        }

        # Write JSONL
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        self._runs.append(record)
        self._run_count += 1

    def log_feedback(self, run_id: str, score: float, comment: str = "",
                     key: str = "user-rating") -> None:
        """Log user feedback for a specific run."""
        feedback_entry = {
            "run_id": run_id,
            "key": key,
            "score": score,
            "comment": comment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._feedback.append(feedback_entry)

        # Also write to JSONL
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            record = {"type": "feedback", **feedback_entry}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ─── Markdown Report Generation ───────────────────────────────────────

    def write_markdown_report(self, question: str = "", thread_id: str = "") -> None:
        """Generate the human-readable Markdown trace report."""
        if not self._runs:
            return

        lines = []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # ── Header ──
        lines.append("# 📊 LangSmith Local Trace Report")
        lines.append("")
        lines.append(f"**Generated:** {now}")
        if question:
            lines.append(f"**Question:** {question}")
        if thread_id:
            lines.append(f"**Thread ID:** `{thread_id}`")
        if self._trace_id:
            lines.append(f"**Trace ID:** `{self._trace_id}`")

        project = next((r.get("project_name") for r in self._runs if r.get("project_name")), "langsmith-research-agent")
        lines.append(f"**Project:** `{project}`")

        # ── Environment Info ──
        if self._env_info:
            env = self._env_info
            lines.append(f"**Environment:** Python `{env.get('python_version', '?')}` • "
                         f"{env.get('os', '?')} ({env.get('machine', '?')})")

        # ── Trace Overview Table ──
        lines.append("## 🌳 Trace Overview")
        lines.append("")
        lines.append("| # | Node | Type | Latency | Tokens (In/Out) | Cost | Finish | Status |")
        lines.append("|---|------|------|---------|-----------------|------|--------|--------|")

        total_latency = 0.0
        total_tokens = 0
        total_cost = 0.0

        for i, run in enumerate(self._runs, 1):
            name = run.get("name", "?")
            rtype = run.get("run_type", "?")
            meta = run.get("metadata") or {}

            # Latency
            latency = run.get("latency_ms")
            if latency is not None:
                lat_str = f"{latency:,.1f}ms"
                total_latency += latency
            else:
                lat_str = "—"

            # Tokens
            usage = run.get("usage_metadata") or {}
            in_tok = usage.get("input_tokens")
            out_tok = usage.get("output_tokens")
            total_tok = usage.get("total_tokens")
            if in_tok is not None and out_tok is not None:
                tok_str = f"{in_tok:,}/{out_tok:,} ({(in_tok + out_tok):,})"
                total_tokens += (in_tok + out_tok)
            elif total_tok:
                tok_str = f"{total_tok:,}"
                total_tokens += total_tok
            else:
                tok_str = "—"

            # Cost
            cost = run.get("estimated_cost_usd")
            cost_str = f"${cost:.6f}" if cost else "—"
            if cost:
                total_cost += cost

            # Finish reason
            finish = run.get("finish_reason", "—") or "—"

            # Status
            status = run.get("status", "?")
            status_icon = "✅" if status == "success" else "❌"

            # Type emoji
            type_icons = {"llm": "🤖", "tool": "🔧", "retriever": "📄", "chain": "🔗"}
            type_icon = type_icons.get(rtype, "⚙️")

            lines.append(f"| {i} | **{name}** | {type_icon} `{rtype}` | "
                         f"{lat_str} | {tok_str} | {cost_str} | `{finish}` | {status_icon} |")

        # Totals row
        lines.append(f"| | **TOTAL** | | **{total_latency:,.1f}ms** | "
                     f"**{total_tokens:,}** | **${total_cost:.6f}** | | |")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ── Detailed Node Sections ──
        lines.append("## 📋 Detailed Run Log")
        lines.append("")

        for i, run in enumerate(self._runs, 1):
            name = run.get("name", "Unknown")
            rtype = run.get("run_type", "?")
            type_icons = {"llm": "🤖", "tool": "🔧", "retriever": "📄", "chain": "🔗"}
            icon = type_icons.get(rtype, "⚙️")

            lines.append(f"### {icon} {i}. {name}")
            lines.append("")

            # Quick facts table
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            lines.append(f"| **Run Type** | `{rtype}` |")
            lines.append(f"| **Run ID** | `{run.get('run_id', '—')}` |")
            if run.get("parent_run_id"):
                lines.append(f"| **Parent Run** | `{run['parent_run_id']}` |")

            meta = run.get("metadata") or {}

            if run.get("latency_ms") is not None:
                lines.append(f"| **Latency** | `{run['latency_ms']:,.1f}ms` ⏱️ *real* |")
            if run.get("thread_id"):
                lines.append(f"| **Thread ID** | `{run['thread_id']}` |")
            if run.get("finish_reason"):
                lines.append(f"| **Finish Reason** | `{run['finish_reason']}` |")
            lines.append(f"| **Status** | `{run.get('status', '?')}` |")
            lines.append("")

            # Tags
            tags = run.get("tags", [])
            if tags:
                tag_badges = " ".join([f"`{t}`" for t in tags])
                lines.append(f"**Tags:** {tag_badges}")
                lines.append("")

            # ls_ Metadata (LangSmith parameters)
            ls_keys = {k: v for k, v in meta.items() if k.startswith("ls_")}
            if ls_keys:
                lines.append("<details>")
                lines.append("<summary><strong>🏷️ LangSmith Parameters</strong></summary>")
                lines.append("")
                lines.append("| Parameter | Value |")
                lines.append("|-----------|-------|")
                for k, v in ls_keys.items():
                    lines.append(f"| `{k}` | `{v}` |")
                lines.append("")
                lines.append("</details>")
                lines.append("")

            # Other Metadata (non-ls_ keys)
            other_meta = {k: v for k, v in meta.items() if not k.startswith("ls_")}
            if other_meta:
                lines.append("<details>")
                lines.append("<summary><strong>📎 Metadata</strong></summary>")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(other_meta, indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("</details>")
                lines.append("")

            # LLM Prompts & Completion
            prompts = run.get("llm_prompts")
            completion = run.get("llm_completion")
            if prompts:
                lines.append("**💬 LLM Prompts:**")
                lines.append("")
                for msg in prompts:
                    role = msg.get("role", "unknown").upper()
                    content = msg.get("content", "")
                    lines.append(f"> **{role}:**")
                    for pline in content.split("\n"):
                        lines.append(f"> {pline}")
                    lines.append(">")
                lines.append("")

            if completion:
                lines.append("**✅ LLM Completion:**")
                lines.append("")
                lines.append("```")
                lines.append(completion)
                lines.append("```")
                lines.append("")

            # Token usage (with detail breakdowns)
            usage = run.get("usage_metadata") or {}
            if usage:
                lines.append("**📊 Token Usage** *(from Google API — real values)*")
                lines.append("")
                lines.append("| Metric | Count |")
                lines.append("|--------|-------|")
                # Core metrics first
                for key in ["input_tokens", "output_tokens", "total_tokens"]:
                    if key in usage:
                        display_k = key.replace("_", " ").title()
                        lines.append(f"| {display_k} | `{usage[key]:,}` |")

                # Token detail breakdowns (cache_read, reasoning, etc.)
                for detail_key in ["input_token_details", "output_token_details"]:
                    details = usage.get(detail_key)
                    if details and isinstance(details, dict):
                        for dk, dv in details.items():
                            if dv:  # Only show non-zero/non-null
                                display = f"{detail_key.split('_')[0].title()} → {dk.replace('_', ' ').title()}"
                                lines.append(f"| {display} | `{dv:,}` |")

                # Any other usage fields
                for k, v in usage.items():
                    if k not in ("input_tokens", "output_tokens", "total_tokens",
                                 "input_token_details", "output_token_details"):
                        display_k = k.replace("_", " ").title()
                        lines.append(f"| {display_k} | `{v}` |")
                lines.append("")

            if run.get("estimated_cost_usd") is not None:
                lines.append(f"**💰 Cost:** `${run['estimated_cost_usd']:.6f}` "
                             "*(calculated from real token counts)*")
                lines.append("")

            # Response Metadata (finish reason, safety, model)
            resp_meta = run.get("response_metadata") or {}
            if resp_meta:
                # Safety ratings (Gemini-specific)
                safety = resp_meta.get("safety_ratings")
                if safety and isinstance(safety, list):
                    lines.append("<details>")
                    lines.append("<summary><strong>🛡️ Safety Ratings</strong></summary>")
                    lines.append("")
                    lines.append("| Category | Probability |")
                    lines.append("|----------|-------------|")
                    for rating in safety:
                        if isinstance(rating, dict):
                            cat = rating.get("category", "?")
                            prob = rating.get("probability", "?")
                            lines.append(f"| `{cat}` | `{prob}` |")
                    lines.append("")
                    lines.append("</details>")
                    lines.append("")

            # Inputs (collapsible)
            inputs = run.get("inputs")
            if inputs:
                lines.append("<details>")
                lines.append("<summary><strong>📥 Inputs</strong></summary>")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(inputs, indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("</details>")
                lines.append("")

            # Outputs (collapsible)
            outputs = run.get("outputs")
            if outputs:
                lines.append("<details>")
                lines.append("<summary><strong>📤 Outputs</strong></summary>")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(outputs, indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("</details>")
                lines.append("")

            # Retrieved Documents (special rendering per LangSmith spec)
            ret_docs = run.get("retrieved_documents")
            if ret_docs:
                lines.append(f"**📄 Retrieved Documents ({len(ret_docs)}):**")
                lines.append("")
                for di, doc in enumerate(ret_docs, 1):
                    src = doc.get("metadata", {}).get("source", "Unknown")
                    page = doc.get("metadata", {}).get("page", "?")
                    score = doc.get("metadata", {}).get("relevance_score", "?")
                    doc_type = doc.get("type", "?")
                    lines.append(f"**Doc {di}** — `{src}` (page {page}, "
                                 f"score: {score}, type: `{doc_type}`)")
                    lines.append("")
                    content = doc.get("page_content", "")
                    lines.append(f"> {content}")
                    lines.append("")

            # Feedback
            feedback = run.get("feedback")
            if feedback:
                lines.append("**⭐ Feedback:**")
                lines.append("")
                lines.append("| Key | Score | Comment |")
                lines.append("|-----|-------|---------|")
                if isinstance(feedback, dict):
                    lines.append(f"| `{feedback.get('key', '—')}` | "
                                 f"`{feedback.get('score', '—')}` | "
                                 f"{feedback.get('comment', '—')} |")
                lines.append("")

            # Error (full traceback)
            if run.get("error"):
                lines.append("**❌ Error:**")
                lines.append("")
                lines.append("```")
                lines.append(str(run["error"]))
                lines.append("```")
                lines.append("")

            lines.append("---")
            lines.append("")

        # ── Feedback Section ──
        if self._feedback:
            lines.append("## ⭐ User Feedback")
            lines.append("")
            lines.append("| Run ID | Key | Score | Comment | Time |")
            lines.append("|--------|-----|-------|---------|------|")
            for fb in self._feedback:
                lines.append(f"| `{fb['run_id'][:12]}...` | `{fb['key']}` | "
                             f"`{fb['score']}` | {fb.get('comment', '—')} | "
                             f"`{fb['timestamp']}` |")
            lines.append("")
            lines.append("---")
            lines.append("")

        # ── Footer ──
        lines.append(f"*Local trace report • {len(self._runs)} runs • {now}*")

        # Write the file
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"📄 [LocalFileLogger] Markdown report written to: {os.path.abspath(self.md_path)}")

    # ─── Utilities ────────────────────────────────────────────────────────

    def get_summary(self) -> str:
        """Return a summary of the logging session."""
        return (
            f"📝 {self._run_count} runs logged\n"
            f"   JSONL → {self.jsonl_path}\n"
            f"   MD   → {self.md_path}"
        )

    def read_last_n(self, n: int = 5) -> list[dict]:
        """Read the last N entries from the JSONL file."""
        if not os.path.exists(self.jsonl_path):
            return []
        with open(self.jsonl_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        entries = []
        for line in all_lines[-n:]:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                pass
        return entries

    def print_summary_table(self, n: int = 10) -> None:
        """Print a formatted console summary of the last N logged runs."""
        entries = self.read_last_n(n)
        if not entries:
            print("   (no entries found)")
            return

        print(f"\n   {'#':<4} {'Name':<22} {'Type':<10} {'Latency':<10} {'Tokens':<8} {'Status':<8}")
        print(f"   {'─'*4} {'─'*22} {'─'*10} {'─'*10} {'─'*8} {'─'*8}")
        for i, entry in enumerate(entries, 1):
            name = (entry.get("name", "?"))[:21]
            rtype = entry.get("run_type", "?")
            latency = entry.get("latency_ms")
            lat_str = f"{latency:,.0f}ms" if latency else "—"
            usage = entry.get("usage_metadata") or {}
            tokens = usage.get("total_tokens", "—")
            status = "✅" if entry.get("status") == "success" else "❌"
            print(f"   {i:<4} {name:<22} {rtype:<10} {lat_str:<10} {tokens:<8} {status:<8}")
