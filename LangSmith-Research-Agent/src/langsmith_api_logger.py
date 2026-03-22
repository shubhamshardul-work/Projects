"""
LangSmith API Logger — Fetches trace data from LangSmith cloud and generates local reports.

This logger uses the LangSmith Python SDK (langsmith.Client) to pull
all run data for a given trace after execution. It generates:
1. A Markdown report mirroring what you'd see in the LangSmith UI
2. A JSONL file with raw run data for programmatic analysis

This is completely independent of the local logger (local_logger.py).
"""

import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional


class LangSmithAPILogger:
    """
    Fetches trace data from the LangSmith API and generates local reports.

    Requires:
    - LANGSMITH_API_KEY environment variable
    - LANGSMITH_TRACING=true (so traces are actually sent to the cloud)
    """

    def __init__(self, output_dir: str = "logs"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self._client = None

    def _get_client(self):
        """Lazy-init the LangSmith client."""
        if self._client is None:
            from langsmith import Client
            self._client = Client()
        return self._client

    # ─── Wait for Trace Ingestion ─────────────────────────────────────────

    def _wait_for_trace(self, trace_id: str, max_wait_sec: int = 10) -> bool:
        """
        Poll LangSmith until the trace is fully ingested.

        LangSmith ingests traces asynchronously, so there's a short delay
        between graph.invoke() returning and the data being queryable.
        """
        client = self._get_client()
        print(f"⏳ [LangSmith API Logger] Waiting for trace {trace_id[:12]}... to be ingested...")

        for attempt in range(max_wait_sec):
            try:
                runs = list(client.list_runs(
                    trace_id=trace_id,
                    is_root=True,
                    limit=1,
                ))
                if runs and runs[0].end_time is not None:
                    # Root run is complete — wait a bit more for children
                    time.sleep(2)
                    print(f"✅ [LangSmith API Logger] Trace found after {attempt + 1}s")
                    return True
            except Exception:
                pass
            time.sleep(1)

        print(f"⚠️  [LangSmith API Logger] Trace not found after {max_wait_sec}s, proceeding anyway")
        return False

    # ─── Fetch Data ───────────────────────────────────────────────────────

    def _fetch_runs(self, trace_id: str) -> list:
        """Fetch all runs for a trace, sorted by start_time."""
        client = self._get_client()
        runs = list(client.list_runs(trace_id=trace_id))
        runs.sort(key=lambda r: r.start_time)
        return runs

    def _fetch_feedback(self, run_ids: list) -> list:
        """Fetch feedback for the given run IDs."""
        if not run_ids:
            return []
        client = self._get_client()
        try:
            return list(client.list_feedback(run_ids=run_ids))
        except Exception:
            return []

    # ─── Helpers ──────────────────────────────────────────────────────────

    def _compute_depth(self, run) -> int:
        """Compute nesting depth from parent_run_ids chain."""
        if run.parent_run_ids:
            return len(run.parent_run_ids)
        elif run.parent_run_id:
            return 1
        return 0

    def _get_latency_ms(self, run) -> Optional[float]:
        """Compute latency in ms from start/end times."""
        if run.start_time and run.end_time:
            delta = run.end_time - run.start_time
            return round(delta.total_seconds() * 1000, 1)
        return None

    def _get_metadata(self, run) -> dict:
        """Extract metadata from run.extra."""
        if run.extra and isinstance(run.extra, dict):
            return run.extra.get("metadata", {}) or {}
        return {}

    def _get_run_url(self, run) -> Optional[str]:
        """Get the LangSmith UI URL for a run."""
        try:
            client = self._get_client()
            return client.get_run_url(run=run)
        except Exception:
            return None

    def _safe(self, obj: Any) -> Any:
        """Make an object JSON-serializable."""
        if obj is None:
            return None
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: self._safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._safe(item) for item in obj]
        try:
            return str(obj)
        except Exception:
            return repr(obj)

    def _extract_prompts(self, run) -> list:
        """Extract LLM prompts from run.inputs."""
        inputs = run.inputs or {}
        # LangChain stores messages under various keys
        messages = inputs.get("messages") or inputs.get("prompts") or []
        result = []
        if isinstance(messages, list):
            for msg in messages:
                if isinstance(msg, dict):
                    result.append(msg)
                elif isinstance(msg, list):
                    # Nested list of messages (LangChain format)
                    for m in msg:
                        if isinstance(m, dict):
                            role = m.get("type", m.get("role", "unknown"))
                            content = m.get("content", m.get("text", ""))
                            result.append({"role": role, "content": content})
        return result

    def _extract_completion(self, run) -> Optional[str]:
        """Extract LLM completion text from run.outputs."""
        outputs = run.outputs or {}
        # Try various output formats
        if "output" in outputs:
            out = outputs["output"]
            if isinstance(out, dict):
                return out.get("content", str(out))
            return str(out)
        if "generations" in outputs:
            gens = outputs["generations"]
            if isinstance(gens, list) and gens:
                gen = gens[0] if isinstance(gens[0], list) else gens
                if isinstance(gen, list) and gen:
                    return gen[0].get("text", "") if isinstance(gen[0], dict) else str(gen[0])
        return None

    # ─── Main Entry Point ─────────────────────────────────────────────────

    def fetch_and_log(self, trace_id: str, question: str = "",
                      thread_id: str = "", max_wait_sec: int = 10) -> Optional[str]:
        """
        Main entry point: fetch trace from LangSmith API → generate reports.

        Returns the path to the generated Markdown file, or None on failure.
        """
        try:
            self._wait_for_trace(trace_id, max_wait_sec)

            runs = self._fetch_runs(trace_id)
            if not runs:
                print("⚠️  [LangSmith API Logger] No runs found for trace")
                return None

            run_ids = [run.id for run in runs]
            feedback = self._fetch_feedback(run_ids)

            # Generate report
            report = self._generate_report(runs, feedback, question, thread_id, trace_id)

            # Write files
            md_path = os.path.join(self.output_dir, f"langsmith_api_trace_{str(trace_id)[:12]}.md")
            jsonl_path = os.path.join(self.output_dir, f"langsmith_api_trace_{str(trace_id)[:12]}.jsonl")

            with open(md_path, "w", encoding="utf-8") as f:
                f.write(report)

            with open(jsonl_path, "w", encoding="utf-8") as f:
                for run in runs:
                    record = self._run_to_dict(run)
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

            print(f"📄 [LangSmith API Logger] Markdown → {os.path.abspath(md_path)}")
            print(f"📄 [LangSmith API Logger] JSONL    → {os.path.abspath(jsonl_path)}")
            return md_path

        except Exception as e:
            print(f"⚠️  [LangSmith API Logger] Failed: {e}")
            return None

    # ─── Run → Dict (for JSONL) ───────────────────────────────────────────

    def _run_to_dict(self, run) -> dict:
        """Convert a Run object to a JSON-serializable dict."""
        return {
            "id": str(run.id),
            "name": run.name,
            "run_type": run.run_type,
            "trace_id": str(run.trace_id),
            "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
            "dotted_order": run.dotted_order,
            "status": run.status,
            "error": run.error,
            "start_time": self._safe(run.start_time),
            "end_time": self._safe(run.end_time),
            "latency_ms": self._get_latency_ms(run),
            "first_token_time": self._safe(run.first_token_time),
            "inputs": self._safe(run.inputs),
            "outputs": self._safe(run.outputs),
            "prompt_tokens": run.prompt_tokens,
            "completion_tokens": run.completion_tokens,
            "total_tokens": run.total_tokens,
            "prompt_token_details": self._safe(run.prompt_token_details),
            "completion_token_details": self._safe(run.completion_token_details),
            "total_cost": float(run.total_cost) if run.total_cost else None,
            "prompt_cost": float(run.prompt_cost) if run.prompt_cost else None,
            "completion_cost": float(run.completion_cost) if run.completion_cost else None,
            "prompt_cost_details": self._safe(run.prompt_cost_details),
            "completion_cost_details": self._safe(run.completion_cost_details),
            "tags": run.tags,
            "metadata": self._get_metadata(run),
            "extra": self._safe(run.extra),
            "events": self._safe(run.events),
            "feedback_stats": self._safe(run.feedback_stats),
            "child_run_ids": [str(cid) for cid in run.child_run_ids] if run.child_run_ids else None,
            "session_id": str(run.session_id) if run.session_id else None,
            "app_path": run.app_path,
            "in_dataset": run.in_dataset,
            "depth": self._compute_depth(run),
        }

    # ─── Markdown Report Generation ───────────────────────────────────────

    def _generate_report(self, runs: list, feedback: list,
                         question: str, thread_id: str, trace_id: str) -> str:
        """Generate a comprehensive Markdown trace report from LangSmith API data."""
        lines = []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # ── Header ──
        lines.append("# 📊 LangSmith API Trace Report")
        lines.append("")
        lines.append(f"**Generated:** {now}")
        lines.append(f"**Data Source:** LangSmith Cloud API (`langsmith.Client`)")
        if question:
            lines.append(f"**Question:** {question}")
        if thread_id:
            lines.append(f"**Thread ID:** `{thread_id}`")
        lines.append(f"**Trace ID:** `{trace_id}`")

        # Project name
        if runs and runs[0].session_id:
            lines.append(f"**Session ID:** `{runs[0].session_id}`")

        # LangSmith UI link for root run
        root_runs = [r for r in runs if r.parent_run_id is None]
        if root_runs:
            url = self._get_run_url(root_runs[0])
            if url:
                lines.append(f"**🔗 View in LangSmith:** [{url}]({url})")

        lines.append("")
        lines.append("---")
        lines.append("")

        # ── Trace Overview Table ──
        lines.append("## 🌳 Trace Overview")
        lines.append("")
        lines.append("| # | Depth | Node | Type | Latency | Tokens (In/Out) | Cost | Status |")
        lines.append("|---|-------|------|------|---------|-----------------|------|--------|")

        total_latency = 0.0
        total_tokens = 0
        total_cost = 0.0

        for i, run in enumerate(runs, 1):
            depth = self._compute_depth(run)
            indent = "→ " * depth if depth > 0 else ""
            name = f"{indent}{run.name}"
            rtype = run.run_type or "?"

            latency = self._get_latency_ms(run)
            lat_str = f"{latency:,.1f}ms" if latency is not None else "—"
            if latency:
                total_latency += latency

            pt = run.prompt_tokens or 0
            ct = run.completion_tokens or 0
            tt = run.total_tokens or 0
            if pt or ct:
                tok_str = f"{pt:,}/{ct:,} ({tt:,})"
                total_tokens += tt
            elif tt:
                tok_str = f"{tt:,}"
                total_tokens += tt
            else:
                tok_str = "—"

            cost = float(run.total_cost) if run.total_cost else 0
            cost_str = f"${cost:.6f}" if cost else "—"
            total_cost += cost

            status = run.status or "?"
            status_icon = "✅" if status == "success" else "❌" if status == "error" else "⏳"

            type_icons = {"llm": "🤖", "tool": "🔧", "retriever": "📄", "chain": "🔗"}
            type_icon = type_icons.get(rtype, "⚙️")

            lines.append(f"| {i} | {depth} | **{name}** | {type_icon} `{rtype}` | "
                         f"{lat_str} | {tok_str} | {cost_str} | {status_icon} |")

        lines.append(f"| | | **TOTAL** | | **{total_latency:,.1f}ms** | "
                     f"**{total_tokens:,}** | **${total_cost:.6f}** | |")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ── Detailed Run Log ──
        lines.append("## 📋 Detailed Run Log")
        lines.append("")

        for i, run in enumerate(runs, 1):
            rtype = run.run_type or "?"
            type_icons = {"llm": "🤖", "tool": "🔧", "retriever": "📄", "chain": "🔗"}
            icon = type_icons.get(rtype, "⚙️")
            depth = self._compute_depth(run)

            lines.append(f"### {icon} {i}. {run.name}")
            lines.append("")

            # Quick facts
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            lines.append(f"| **Run Type** | `{rtype}` |")
            lines.append(f"| **Run ID** | `{run.id}` |")
            if run.parent_run_id:
                lines.append(f"| **Parent Run** | `{run.parent_run_id}` |")
            lines.append(f"| **Depth** | `{depth}` |")
            if run.start_time:
                lines.append(f"| **Start Time** | `{run.start_time.isoformat()}` |")
            if run.end_time:
                lines.append(f"| **End Time** | `{run.end_time.isoformat()}` |")
            latency = self._get_latency_ms(run)
            if latency is not None:
                lines.append(f"| **Latency** | `{latency:,.1f}ms` |")
            if run.first_token_time:
                ttft = (run.first_token_time - run.start_time).total_seconds() * 1000
                lines.append(f"| **Time to First Token** | `{ttft:,.1f}ms` |")
            lines.append(f"| **Status** | `{run.status or '?'}` |")

            # LangSmith UI link
            url = self._get_run_url(run)
            if url:
                lines.append(f"| **🔗 LangSmith** | [View Run]({url}) |")
            lines.append("")

            # Tags
            if run.tags:
                tag_badges = " ".join([f"`{t}`" for t in run.tags])
                lines.append(f"**Tags:** {tag_badges}")
                lines.append("")

            # Metadata (ls_ params)
            meta = self._get_metadata(run)
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

            # Other metadata
            other_meta = {k: v for k, v in meta.items() if not k.startswith("ls_")}
            if other_meta:
                lines.append("<details>")
                lines.append("<summary><strong>📎 Metadata</strong></summary>")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(self._safe(other_meta), indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("</details>")
                lines.append("")

            # LLM Prompts & Completion
            if rtype == "llm":
                prompts = self._extract_prompts(run)
                completion = self._extract_completion(run)

                if prompts:
                    lines.append("**💬 LLM Prompts:**")
                    lines.append("")
                    for msg in prompts:
                        role = msg.get("type", msg.get("role", "unknown")).upper()
                        content = msg.get("content", msg.get("text", ""))
                        lines.append(f"> **{role}:**")
                        if isinstance(content, str):
                            for pline in content.split("\n"):
                                lines.append(f"> {pline}")
                        else:
                            lines.append(f"> {content}")
                        lines.append(">")
                    lines.append("")

                if completion:
                    lines.append("**✅ LLM Completion:**")
                    lines.append("")
                    lines.append("```")
                    lines.append(completion)
                    lines.append("```")
                    lines.append("")

            # Token Usage
            pt = run.prompt_tokens
            ct = run.completion_tokens
            tt = run.total_tokens
            if pt or ct or tt:
                lines.append("**📊 Token Usage** *(from LangSmith API)*")
                lines.append("")
                lines.append("| Metric | Count |")
                lines.append("|--------|-------|")
                if pt is not None:
                    lines.append(f"| Prompt Tokens | `{pt:,}` |")
                if ct is not None:
                    lines.append(f"| Completion Tokens | `{ct:,}` |")
                if tt is not None:
                    lines.append(f"| Total Tokens | `{tt:,}` |")

                # Token detail breakdowns
                if run.prompt_token_details:
                    for dk, dv in run.prompt_token_details.items():
                        if dv:
                            lines.append(f"| Prompt → {dk.replace('_', ' ').title()} | `{dv:,}` |")
                if run.completion_token_details:
                    for dk, dv in run.completion_token_details.items():
                        if dv:
                            lines.append(f"| Completion → {dk.replace('_', ' ').title()} | `{dv:,}` |")
                lines.append("")

            # Cost
            tc = run.total_cost
            pc = run.prompt_cost
            cc = run.completion_cost
            if tc or pc or cc:
                lines.append("**💰 Cost** *(from LangSmith model pricing map)*")
                lines.append("")
                lines.append("| Metric | Amount |")
                lines.append("|--------|--------|")
                if pc is not None:
                    lines.append(f"| Prompt Cost | `${float(pc):.8f}` |")
                if cc is not None:
                    lines.append(f"| Completion Cost | `${float(cc):.8f}` |")
                if tc is not None:
                    lines.append(f"| **Total Cost** | `${float(tc):.8f}` |")

                # Cost detail breakdowns
                if run.prompt_cost_details:
                    for dk, dv in run.prompt_cost_details.items():
                        if dv:
                            lines.append(f"| Prompt → {dk.replace('_', ' ').title()} | `${float(dv):.8f}` |")
                if run.completion_cost_details:
                    for dk, dv in run.completion_cost_details.items():
                        if dv:
                            lines.append(f"| Completion → {dk.replace('_', ' ').title()} | `${float(dv):.8f}` |")
                lines.append("")

            # Retrieved Documents (for retriever runs)
            if rtype == "retriever" and run.outputs:
                docs = run.outputs.get("documents") or run.outputs.get("output") or []
                if isinstance(docs, list) and docs:
                    lines.append(f"**📄 Retrieved Documents ({len(docs)}):**")
                    lines.append("")
                    for di, doc in enumerate(docs, 1):
                        if isinstance(doc, dict):
                            src = doc.get("metadata", {}).get("source", "Unknown")
                            page = doc.get("metadata", {}).get("page", "?")
                            score = doc.get("metadata", {}).get("relevance_score", "?")
                            content = doc.get("page_content", "")
                            lines.append(f"**Doc {di}** — `{src}` (page {page}, score: {score})")
                            lines.append("")
                            lines.append(f"> {content}")
                            lines.append("")

            # Inputs (collapsible)
            if run.inputs:
                lines.append("<details>")
                lines.append("<summary><strong>📥 Inputs</strong></summary>")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(self._safe(run.inputs), indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("</details>")
                lines.append("")

            # Outputs (collapsible)
            if run.outputs:
                lines.append("<details>")
                lines.append("<summary><strong>📤 Outputs</strong></summary>")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(self._safe(run.outputs), indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("</details>")
                lines.append("")

            # Events
            if run.events:
                lines.append("<details>")
                lines.append("<summary><strong>📡 Events</strong></summary>")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(self._safe(run.events), indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("</details>")
                lines.append("")

            # Error
            if run.error:
                lines.append("**❌ Error:**")
                lines.append("")
                lines.append("```")
                lines.append(run.error)
                lines.append("```")
                lines.append("")

            # Feedback stats
            if run.feedback_stats:
                lines.append("<details>")
                lines.append("<summary><strong>⭐ Feedback Stats</strong></summary>")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(self._safe(run.feedback_stats), indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("</details>")
                lines.append("")

            lines.append("---")
            lines.append("")

        # ── Feedback Section ──
        if feedback:
            lines.append("## ⭐ User Feedback")
            lines.append("")
            lines.append("| Run ID | Key | Score | Comment |")
            lines.append("|--------|-----|-------|---------|")
            for fb in feedback:
                run_id_short = str(fb.run_id)[:12] + "..." if fb.run_id else "—"
                lines.append(f"| `{run_id_short}` | `{fb.key}` | "
                             f"`{fb.score}` | {fb.comment or '—'} |")
            lines.append("")
            lines.append("---")
            lines.append("")

        # ── Footer ──
        lines.append(f"*LangSmith API trace report • {len(runs)} runs • "
                     f"Total cost: ${total_cost:.6f} • {now}*")

        return "\n".join(lines)
