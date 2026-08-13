"""cli — the presentation + entry layer. The pure (Streamlit-free) presenter/formatting helpers,
the Markdown leadership digest, and the argparse CLI runner + portfolio roll-up + fixture/
snapshot builders. This is the top of the dependency stack."""


import argparse
import asyncio
import csv
import json
import logging
import os
import re
import shlex
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default as _default_policy
from email.utils import format_datetime, parsedate_to_datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional, TypedDict
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.types import RetryPolicy
from pydantic import BaseModel, Field, model_validator


from fieldora.core import *
from fieldora.sources import list_accounts, build_all
from fieldora.agent import grounding_summary, run_account, run_batch, evals_main




# ══════════════════════════════════════════════════════════════════════════════
# PRESENTER — pure (Streamlit-free) view + formatting helpers
# ══════════════════════════════════════════════════════════════════════════════
# Turns a pipeline AgentState into a plain, JSON-able "view" dict, and provides the formatting /
# roll-up helpers the CLI and the Streamlit shell render. Keeping this Streamlit-free means the same
# view shape powers live rendering, session caching, AND on-disk snapshots (Replay mode).
#
# Palette note (dataviz method): RAG is a *status* palette — reserved colours that ship alongside an
# icon + text label, so meaning never rides on colour alone. Magnitude bars use a single hue + length.


RAG_COLOR = {"RED": "#D64545", "AMBER": "#E0A100", "GREEN": "#2E9D63"}
RAG_TINT = {"RED": "#FBEAEA", "AMBER": "#FBF3DE", "GREEN": "#E8F5EE"}   # banner backgrounds
RAG_ICON = {"RED": "🔴", "AMBER": "🟡", "GREEN": "🟢"}
MAGNITUDE_HUE = "#2C7A7B"      # teal — one hue for length-encoded bars (matches the theme)
NEUTRAL_INK = "#5B6570"


# Sidebar source keys → human labels (for the provenance strip).
SOURCE_LABELS = {"CRM_MODE": "CRM", "PLATFORM_MODE": "Platform", "SUPPORT_MODE": "Support",
                 "EMAIL_MODE": "Email", "SLACK_MODE": "Slack"}




def rag_color(rag: str) -> str:
    return RAG_COLOR.get(rag, NEUTRAL_INK)




def rag_tint(rag: str) -> str:
    return RAG_TINT.get(rag, "#F0F3F4")




def rag_icon(rag: str) -> str:
    return RAG_ICON.get(rag, "⚪")




def money(n) -> str:
    return f"${n:,.0f}" if n is not None else "—"




def money_short(n) -> str:
    """Compact money for KPI tiles: $1.2M / $600K / $900."""
    if n is None:
        return "—"
    n = float(n)
    if abs(n) >= 1_000_000:
        return f"${n / 1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"${n / 1_000:.0f}K"
    return f"${n:.0f}"




def provenance(modes: dict) -> list[str]:
    """['CRM: csv', 'Platform: sqlite', …] from the source-mode map (values may carry a suffix)."""
    return [f"{SOURCE_LABELS[k]}: {str(v).split()[0]}" for k, v in modes.items() if k in SOURCE_LABELS]




def flags(signals: dict) -> list[dict]:
    """The headline signals to surface as pills: competitor mentions + churn phrases (short quotes).
    (Stakeholder changes stay full finding-cards because they carry citations.)"""
    s = signals or {}
    out = [{"kind": "Competitor", "text": q} for q in s.get("competitor_mentions", [])]
    out += [{"kind": "Churn", "text": q} for q in s.get("churn_signals", [])]
    return out




def delta_str(health: dict) -> str:
    """Week-over-week label from a health view dict."""
    d = (health or {}).get("delta")
    if d is None:
        return "baseline set"
    if d > 0:
        return f"▲ +{d} vs last week"
    if d < 0:
        return f"▼ {d} vs last week"
    return "▬ no change"




def to_view(state: dict) -> dict:
    """Flatten an AgentState (with Pydantic objects) into a plain, serializable view dict.


    Runs the grounding summary here (needs the ExtractedSignals object), so everything downstream —
    rendering, caching, snapshots — works off plain data and never touches Pydantic or re-grounds.
    """
    account = state.get("account")
    signals = state.get("signals")
    health = state.get("health")
    brief = state.get("brief")


    a = account.model_dump() if account is not None else {}
    comms = a.get("recent_comms", []) or []


    if signals is not None:
        raw = "\n\n".join(comms)
        total, grounded, unsupported = grounding_summary(signals, raw)
        grounding_view = {"total": total, "grounded": grounded, "unsupported": unsupported}
    else:
        grounding_view = {"total": 0, "grounded": 0, "unsupported": []}


    return {
        "account_id": state.get("account_id"),
        "account": {
            "name": a.get("name"), "csm": a.get("csm"),
            "industry": a.get("industry"), "region": a.get("region"), "stage": a.get("stage"),
            "acv_usd": a.get("acv_usd"), "days_to_renewal": a.get("days_to_renewal"),
            "open_tickets": a.get("open_tickets"),
            "modules_licensed": a.get("modules_licensed"), "modules_active": a.get("modules_active"),
        },
        "raw_comms": comms,
        "health": health.model_dump() if health is not None else None,
        "signals": signals.model_dump() if signals is not None else None,
        "brief": brief.model_dump() if brief is not None else None,
        "grounding": grounding_view,
        "usage": state.get("usage") or {},
        "latency_s": state.get("latency_s"),
        "attempts": state.get("attempts"),
    }




def component_rows(components: dict) -> list[dict]:
    """Health sub-scores as chart rows (0-100), ordered for a stable bar layout."""
    order = ["adoption", "engagement", "recency", "friction", "sentiment", "milestone"]
    comps = components or {}
    return [{"component": k, "score": comps.get(k, 0)} for k in order if k in comps]




def portfolio_summary(views: dict) -> dict:
    """Aggregate a {account_id: view} map into the leadership rollup numbers."""
    scored = [v for v in views.values() if v.get("health")]
    total_acv = sum((v["account"]["acv_usd"] or 0) for v in scored)
    by_status = {"RED": [], "AMBER": [], "GREEN": []}
    for v in scored:
        by_status.setdefault(v["health"]["rag_status"], []).append(v)


    at_risk = sum((v["account"]["acv_usd"] or 0) for v in by_status.get("RED", []))
    churn_budget = total_acv * (1 - GRR_TARGET)


    per_csm: dict[str, dict] = {}
    for v in scored:
        csm = v["account"]["csm"] or "—"
        row = per_csm.setdefault(csm, {"csm": csm, "accounts": 0, "RED": 0, "AMBER": 0,
                                       "GREEN": 0, "at_risk": 0})
        row["accounts"] += 1
        rag = v["health"]["rag_status"]
        row[rag] = row.get(rag, 0) + 1
        if rag == "RED":
            row["at_risk"] += v["account"]["acv_usd"] or 0


    return {
        "counts": {k: len(by_status.get(k, [])) for k in ("RED", "AMBER", "GREEN")},
        "total": len(scored),
        "total_acv": total_acv,
        "at_risk_acv": at_risk,
        "churn_budget": churn_budget,
        "exceeds_budget": at_risk > churn_budget,
        "per_csm": sorted(per_csm.values(), key=lambda r: r["at_risk"], reverse=True),
        "attention": sorted(by_status.get("RED", []),
                            key=lambda v: v["account"]["days_to_renewal"] or 0),
    }




def book_rows(views: dict) -> list[dict]:
    """One flat row per account for the sortable book-of-business table."""
    rows = []
    for v in views.values():
        h = v.get("health") or {}
        a = v["account"]
        rows.append({
            "account_id": v["account_id"], "name": a["name"], "csm": a["csm"],
            "rag": h.get("rag_status", "—"), "score": h.get("score"),
            "adoption_%": h.get("adoption_pct"), "renewal_d": a["days_to_renewal"],
            "acv": a["acv_usd"],
        })
    return sorted(rows, key=lambda r: (r["score"] is None, r["score"] or 0))




def load_snapshots(path=None) -> dict:
    """Load all saved views as {account_id: view} from the snapshots bundle. Empty if none built yet."""
    path = Path(path or SNAPSHOTS_JSON)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))




def save_snapshot(view: dict, path=None) -> None:
    """Upsert one view into the snapshots bundle (read-modify-write of the single JSON file)."""
    path = Path(path or SNAPSHOTS_JSON)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_snapshots(path)
    data[view["account_id"]] = view
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")




# ══════════════════════════════════════════════════════════════════════════════
# REPORTING — Markdown leadership digest ("Monday-morning CS report")
# ══════════════════════════════════════════════════════════════════════════════


_STATUS = {"RED": "🔴", "AMBER": "🟡", "GREEN": "🟢"}




def _report_delta(h) -> str:
    if h.delta is None:
        return "—"
    if h.delta > 0:
        return f"▲ +{h.delta}"
    if h.delta < 0:
        return f"▼ {h.delta}"
    return "▬ 0"




def build_markdown(results: list[dict]) -> str:
    total_acv = sum(r["account"].acv_usd for r in results)
    by = {"RED": [], "AMBER": [], "GREEN": []}
    for r in results:
        by[r["health"].rag_status].append(r)
    at_risk = sum(r["account"].acv_usd for r in by["RED"])
    budget = total_acv * (1 - GRR_TARGET)


    L = []
    L.append(f"# Weekly CS Health Report — {date.today().isoformat()}")
    L.append("")
    L.append(f"**Portfolio:** {len(results)} accounts · ${total_acv:,} book of business  ")
    L.append(f"**Health mix:** 🔴 {len(by['RED'])}  ·  🟡 {len(by['AMBER'])}  ·  🟢 {len(by['GREEN'])}")
    L.append("")


    L.append("## Revenue at risk")
    L.append("")
    L.append(f"- ACV in RED accounts: **${at_risk:,}** ({at_risk / total_acv * 100:.0f}% of book)")
    L.append(f"- GRR churn budget ({1 - GRR_TARGET:.0%} of book for a {GRR_TARGET:.0%} target): ${budget:,.0f}")
    if at_risk > budget:
        L.append("- ⚠ **At-risk ACV exceeds the churn budget — the GRR target is threatened.**")
    L.append("")


    movers = [r for r in results if r["health"].delta is not None]
    decliners = sorted(movers, key=lambda r: r["health"].delta)[:5]
    if decliners:
        L.append("## Biggest movers this week")
        L.append("")
        L.append("| Account | CSM | Score | Δ vs last week |")
        L.append("|---|---|---|---|")
        for r in decliners:
            a, h = r["account"], r["health"]
            L.append(f"| {a.name} | {a.csm} | {h.score}/100 | {_report_delta(h)} |")
        L.append("")


    L.append("## Immediate attention (RED)")
    L.append("")
    if not by["RED"]:
        L.append("_No RED accounts this week._")
        L.append("")
    for r in sorted(by["RED"], key=lambda r: r["account"].days_to_renewal):
        a, h, b = r["account"], r["health"], r["brief"]
        L.append(f"### 🔴 {a.name} — ${a.acv_usd:,} — renewal in {a.days_to_renewal}d")
        L.append(f"- **Score:** {h.score}/100 ({_report_delta(h)}) · adoption {h.adoption_pct}%")
        L.append(f"- **Where it stands:** {b.headline}")
        L.append(f"- **Action this week:** {b.action}")
        L.append("")


    L.append("## By CSM (GRR variance)")
    L.append("")
    L.append("| CSM | Accounts | 🔴 | 🟡 | 🟢 | $ at risk |")
    L.append("|---|---|---|---|---|---|")
    rows = []
    for csm in sorted({r["account"].csm for r in results}):
        book = [r for r in results if r["account"].csm == csm]
        red = [r for r in book if r["health"].rag_status == "RED"]
        amber = sum(1 for r in book if r["health"].rag_status == "AMBER")
        green = sum(1 for r in book if r["health"].rag_status == "GREEN")
        rows.append((csm, len(book), len(red), amber, green,
                     sum(x["account"].acv_usd for x in red)))
    for csm, n, red, amber, green, ar in sorted(rows, key=lambda x: x[5], reverse=True):
        L.append(f"| {csm} | {n} | {red} | {amber} | {green} | ${ar:,} |")
    L.append("")
    L.append("---")
    L.append("*Generated by the Fieldora CSM Account Intelligence agent. "
             "Score is deterministic (rubric); narratives and drafts are AI-generated "
             "and require CSM review before anything is sent.*")
    return "\n".join(L)




def write_report(results: list[dict], path: str | None = None) -> str:
    """Write the digest to reports/weekly_cs_report.md and return the path."""
    out = Path(path) if path else REPORTS_DIR / "weekly_cs_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_markdown(results), encoding="utf-8")
    return str(out)




# ══════════════════════════════════════════════════════════════════════════════
# CLI — argparse runner + portfolio rollup + fixture/snapshot builders
# ══════════════════════════════════════════════════════════════════════════════


STATUS_ICON = {"RED": "🔴", "AMBER": "🟡", "GREEN": "🟢"}
TYPE_TAG = {"RETENTION": "RETENTION PLAY", "STANDARD": "CHECK-IN", "EXPANSION": "EXPANSION PLAY"}
DIVIDER = "━" * 66




def _cli_delta_str(h) -> str:
    if h.delta is None:
        return "• baseline set"
    if h.delta > 0:
        return f"▲ +{h.delta} vs last week"
    if h.delta < 0:
        return f"▼ {h.delta} vs last week"
    return "▬ no change"




def print_brief(result: dict) -> None:
    a = result["account"]
    h = result["health"]
    b = result["brief"]
    icon = STATUS_ICON.get(h.rag_status, "⚪")


    meta = " · ".join(x for x in (a.industry, a.region, a.stage) if x)
    print(f"\n{DIVIDER}")
    print(f"  {icon}  {a.name}   [{TYPE_TAG.get(b.brief_type, b.brief_type)}]")
    if meta:
        print(f"      {meta}")
    print(f"      CSM: {a.csm}  |  ACV: ${a.acv_usd:,}  |  Renewal: {a.days_to_renewal}d")
    print(f"      Score: {h.score}/100  ({_cli_delta_str(h)})  |  Adoption: {h.adoption_pct}%")
    print(f"      Components: {h.components}")
    if h.rules_fired:
        for r in h.rules_fired:
            print(f"      ⚠ rule: {r}")
    print(DIVIDER)


    print(f"\n  {b.headline}\n")
    print("  SITUATION")
    print(f"  {b.situation}\n")
    print("  RISK SIGNALS")
    for r in b.risks:
        print(f"  •  {r}")
    print(f"\n  ACTION THIS WEEK")
    print(f"  →  {b.action}\n")
    print(f"  DRAFT ({b.brief_type} — review before sending)")
    for line in b.draft.splitlines():
        print(f"  │ {line}")
    print()




def print_raw(result: dict) -> None:
    """Dump the raw, messy source comms — the mess a CSM reads by hand."""
    a = result["account"]
    print(f"\n{DIVIDER}")
    print(f"  RAW SOURCE COMMS — {len(a.recent_comms)} documents across email · Slack · support · CRM")
    print(DIVIDER)
    for doc in a.recent_comms:
        print(doc)
        print()




def print_extraction(result: dict) -> None:
    """The AI's structured, cited read of the raw comms, plus the grounding check."""
    a, s = result["account"], result["signals"]
    raw = "\n\n".join(a.recent_comms)
    total, grounded, unsupported = grounding_summary(s, raw)


    def _clean(quote: str) -> str:
        """Strip any quote marks the model wrapped its verbatim span in, so the display shows a
        single pair (grounding already tolerates these — this is display-only)."""
        return quote.strip().strip('"').strip("'").strip()


    def _quote(source: str, quote: str) -> None:
        print(f'        ↳ {source}: "{_clean(quote)}"')


    print(f"\n{DIVIDER}")
    print(f"  EXTRACTED SIGNAL — AI read of {len(a.recent_comms)} raw documents")
    print(DIVIDER)
    print(f"  Sentiment: {s.sentiment_label} ({s.sentiment_score:+.2f})   ·   overall confidence {s.overall_confidence:.0%}")
    for e in s.sentiment_evidence:
        _quote(e.source, e.quote)


    def _findings(title: str, items) -> None:
        if not items:
            return
        print(f"\n  {title}:")
        for f in sorted(items, key=lambda x: x.confidence, reverse=True):
            flag = "   ⚠ low confidence" if f.confidence < 0.5 else ""
            print(f"    • {f.summary}  ({f.confidence:.0%}){flag}")
            for e in f.evidence:
                _quote(e.source, e.quote)


    def _quotes(title: str, items) -> None:
        if not items:
            return
        print(f"\n  {title}:")
        for q in items:
            print(f'    • "{_clean(q)}"')


    _findings("Risks", s.risks)
    _quotes("Churn signals", s.churn_signals)
    _quotes("Expansion signals", s.expansion_signals)
    _quotes("Competitor mentions", s.competitor_mentions)
    _findings("Blockers", s.blockers)
    _findings("Open asks", s.open_asks)
    _findings("Commitments", s.commitments)
    _findings("Stakeholder changes", s.stakeholder_changes)


    print()
    if total == 0:
        print("  Grounding: no citations produced.")
    elif not unsupported:
        print(f"  ✓ Grounding: all {grounded}/{total} citations verified verbatim against source.")
    else:
        print(f"  ⚠ Grounding: {grounded}/{total} verified — {len(unsupported)} NOT found in source:")
        for u in unsupported:
            print(f"        {u}")
    print(DIVIDER)




def print_portfolio(results: list[dict]) -> None:
    total_acv = sum(r["account"].acv_usd for r in results)
    by_status = {"RED": [], "AMBER": [], "GREEN": []}
    for r in results:
        by_status[r["health"].rag_status].append(r)


    at_risk_acv = sum(r["account"].acv_usd for r in by_status["RED"])
    churn_budget = total_acv * (1 - GRR_TARGET)


    print(f"\n{'=' * 66}")
    print("  PORTFOLIO ROLLUP  (for CS leadership)")
    print(f"{'=' * 66}")
    print(f"  🔴 RED: {len(by_status['RED'])}   "
          f"🟡 AMBER: {len(by_status['AMBER'])}   "
          f"🟢 GREEN: {len(by_status['GREEN'])}   "
          f"Total: {len(results)}")
    print(f"\n  Book of business : ${total_acv:,}")
    print(f"  ACV at risk (RED): ${at_risk_acv:,}  ({at_risk_acv/total_acv*100:.0f}% of book)")
    print(f"  GRR churn budget : ${churn_budget:,.0f}  (10% ceiling for a {GRR_TARGET:.0%} GRR target)")
    if at_risk_acv > churn_budget:
        print(f"  ⚠  At-risk ACV EXCEEDS the churn budget — GRR target is threatened.")


    if by_status["RED"]:
        print(f"\n  IMMEDIATE ATTENTION:")
        for r in sorted(by_status["RED"], key=lambda x: x["account"].days_to_renewal):
            a, h = r["account"], r["health"]
            print(f"  •  {a.name} ({a.csm}) — ${a.acv_usd:,} — {a.days_to_renewal}d to renewal — score {h.score}")


    # Per-CSM breakdown — exposes the "GRR variance between CSMs" the brief calls out.
    print(f"\n  BY CSM (health mix + $ at risk):")
    csms = sorted({r["account"].csm for r in results})
    rows = []
    for csm in csms:
        books = [r for r in results if r["account"].csm == csm]
        red = [r for r in books if r["health"].rag_status == "RED"]
        amber = sum(1 for r in books if r["health"].rag_status == "AMBER")
        green = sum(1 for r in books if r["health"].rag_status == "GREEN")
        at_risk = sum(r["account"].acv_usd for r in red)
        rows.append((csm, len(books), len(red), amber, green, at_risk))
    for csm, n, red, amber, green, at_risk in sorted(rows, key=lambda x: x[5], reverse=True):
        print(f"  •  {csm:<16} {n} accts   🔴{red} 🟡{amber} 🟢{green}   ${at_risk:,} at risk")
    print(f"{'=' * 66}\n")




def _print_usage(results: list[dict]) -> None:
    u = summarize(results)
    if u["total_tokens"]:
        print(f"  Tokens: {u['total_tokens']:,} ({u['input_tokens']:,} in / {u['output_tokens']:,} out) "
              f"across {u['accounts']} extraction(s) · {u['latency_s']:.1f}s of model time\n")




def _build_fixtures() -> None:
    """(Re)generate every data/live fixture and list what was written."""
    build_all()
    print(f"  Live fixtures written under: {LIVE_DIR}")
    for pth in sorted(LIVE_DIR.rglob("*")):
        if pth.is_file():
            print(f"    {pth.relative_to(LIVE_DIR)}")




def _build_snapshots(ids: list[str], concurrency: int = 1) -> None:
    """Pre-generate UI snapshots (Replay mode) into data/snapshots.json. RUNS THE MODEL once per account."""
    print(f"  Building {len(ids)} snapshot(s) → {SNAPSHOTS_JSON}  (this calls the model)")
    states = ([run_account(ids[0])] if len(ids) == 1
              else run_batch(ids, max_concurrency=concurrency))
    data = load_snapshots()   # merge into any existing bundle
    for state in states:
        view = to_view(state)
        data[view["account_id"]] = view
        h = view["health"]
        print(f"    ✓ {view['account_id']}  ({h['rag_status']} {h['score']})")
    SNAPSHOTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")




def _parse_args(argv):
    p = argparse.ArgumentParser(
        prog="fieldora",
        description="Fieldora CSM Account Intelligence — score account health, "
                    "branch by risk, draft the play, and roll up the portfolio.",
    )
    p.add_argument("account_id", nargs="?",
                   help="Analyse a single account (e.g. ACC-003). Omit to run the whole portfolio.")
    p.add_argument("--report", action="store_true",
                   help="After a full run, write reports/weekly_cs_report.md.")
    p.add_argument("--raw", action="store_true",
                   help="For a single account, also dump the raw source comms (the mess) before the AI's extraction.")
    p.add_argument("--concurrency", type=int, default=1, metavar="N",
                   help="Analyse the portfolio with up to N accounts in flight at once (default 1).")
    p.add_argument("--verbose", action="store_true",
                   help="Log per-extraction timing/tokens to the console.")
    p.add_argument("--evals", action="store_true",
                   help="Run the eval loop (rubric golden set + optional LLM check) and exit.")
    p.add_argument("--build-fixtures", action="store_true",
                   help="(Re)generate data/live fixtures for the cred-free live modes and exit.")
    p.add_argument("--build-snapshots", action="store_true",
                   help="Pre-generate UI snapshots (Replay mode) for the account (or whole portfolio) — calls the model — and exit.")
    return p.parse_args(argv)




def main(argv=None) -> None:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    configure_logging(args.verbose)


    # ── sub-commands (each exits after running) ──
    if args.evals:
        sys.exit(evals_main())
    if args.build_fixtures:
        _build_fixtures()
        return
    if args.build_snapshots:
        ids = [args.account_id] if args.account_id else [a["account_id"] for a in list_accounts()]
        _build_snapshots(ids, args.concurrency)
        return


    accounts = list_accounts()
    index = {a["account_id"]: a for a in accounts}


    if args.account_id:
        if args.account_id not in index:
            print(f"\nAccount '{args.account_id}' not found. Available: {', '.join(index)}\n")
            sys.exit(1)
        print(f"\nRunning analysis for {args.account_id}...")
        result = run_account(args.account_id)
        if args.raw:
            print_raw(result)          # the messy input
        print_extraction(result)       # the AI's cited read of it
        print_brief(result)            # the score + drafted play
        _print_usage([result])
        return


    print("\n" + "=" * 66)
    print("  FIELDORA CSM ACCOUNT INTELLIGENCE — WEEKLY RUN")
    print("=" * 66)


    ids = [a["account_id"] for a in accounts]
    if args.concurrency > 1:
        print(f"  Analyzing {len(accounts)} accounts (concurrency={args.concurrency})...")
        results = run_batch(ids, max_concurrency=args.concurrency)
    else:
        results = []
        for a in accounts:
            print(f"\n  Analyzing {a['name']}...")
            results.append(run_account(a["account_id"]))


    for r in results:
        print_brief(r)


    print_portfolio(results)
    _print_usage(results)


    if args.report:
        path = write_report(results)
        print(f"  📄 Weekly report written to: {path}\n")