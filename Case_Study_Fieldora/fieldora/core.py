"""core — foundational layer: canonical paths, the tunable health rubric (config), observability,
the typed Pydantic data contracts, and the week-over-week trend store. No dependency on any
other fieldora module. Importing it loads the project .env once."""


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




# ══════════════════════════════════════════════════════════════════════════════
# CORE — paths
# ══════════════════════════════════════════════════════════════════════════════
# Canonical filesystem locations, resolved from the project root (this file's folder), so no
# section hard-codes a relative path or depends on the current working directory.


PROJECT_ROOT = Path(__file__).resolve().parent.parent   # repo root (parent of the fieldora/ package)


DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
LIVE_DIR = DATA_DIR / "live"                        # generated fixtures for the cred-free live modes (auto-built)


# The data folder is just two files. seed.json is the read-only source of truth (the 30-account
# portfolio + the hero comms corpus + the eval gold labels) bundled together; snapshots.json holds
# every pre-built pipeline run for the UI's Replay mode in one dict. Everything else under data/ —
# the live/ fixtures and trend.json — is generated on demand and need not be shipped.
SEED_JSON = DATA_DIR / "seed.json"                  # accounts + comms corpus + eval gold (read-only source)
SNAPSHOTS_JSON = DATA_DIR / "snapshots.json"        # saved pipeline runs for Replay mode (one bundle)
TREND_JSON = DATA_DIR / "trend.json"                # week-over-week score memory (generated at runtime)


# Load .env from the project root once, so every section (LLM provider selection, connector modes)
# sees it regardless of the current working directory. Silent no-op if the file is absent.
load_dotenv(PROJECT_ROOT / ".env")




# ══════════════════════════════════════════════════════════════════════════════
# CORE — config (the tunable health rubric — the single source of truth)
# ══════════════════════════════════════════════════════════════════════════════
# This IS the "shared, consistent definition of account health" the brief says Fieldora lacks.
# Leadership tunes these numbers in one place and every CSM is scored the exact same way. Nothing
# here calls an LLM — the health score is deterministic, reproducible, and auditable.


# ── Component weights (must sum to 1.0) ───────────────────────────────────────
WEIGHTS = {
    "adoption":   0.10,   # Adoption depth is the strongest churn/expansion predictor (ties to NRR)
    "engagement": 0.25,   # Are people actually logging in and using it?
    "recency":    0.15,   # Has the CSM been in contact recently?
    "friction":   0.05,   # Open support tickets = active pain
    "sentiment":  0.10,   # Tone of recent emails/Slack (LLM-derived)
    "milestone":  0.35,   # Deployment/TTV progress
}


# ── Normalisation targets (turn a raw signal into a 0-100 sub-score) ──────────
ADOPTION_TARGET_PCT      = 80    # % of licensed modules active = "fully healthy"
ENGAGEMENT_TARGET_LOGINS = 20    # logins / 30 days considered healthy
RECENCY_MAX_DAYS         = 30    # days-since-contact at which recency score hits 0
FRICTION_MAX_TICKETS     = 5     # open tickets at which friction score hits 0
MILESTONE_PENALTY        = 0.40  # each delayed milestone removes 40% of the sub-score


# ── RAG bands (applied to the 0-100 health score; higher = healthier) ─────────
RED_MAX   = 39   # 0-39   → RED
AMBER_MAX = 70   # 40-70  → AMBER ; 71-100 → GREEN


# ── Business rules straight from the brief ────────────────────────────────────
ADOPTION_RISK_PCT   = 40   # below 40% adoption at the 6-month mark = at risk
SIX_MONTH_MARK      = 6    # months
RENEWAL_URGENT_DAYS = 90   # under 90 days to renewal amplifies every risk signal


# ── GRR context for the portfolio rollup ──────────────────────────────────────
GRR_TARGET = 0.90   # 90%+ gross revenue retention → 10% is the annual churn budget




# ══════════════════════════════════════════════════════════════════════════════
# CORE — observability (local-first token/latency capture + logging)
# ══════════════════════════════════════════════════════════════════════════════
# Captures token usage + latency per extraction so a run is measurable. Everything logs locally via
# stdlib logging; nothing leaves the machine. Optional LangSmith tracing is env-gated
# (LANGSMITH_TRACING=true) and OFF by default — a deliberate data-governance choice.


logger = logging.getLogger("fieldora")




def configure_logging(verbose: bool = False) -> None:
    """Attach a console handler once. INFO when verbose, else WARNING (quiet by default)."""
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("  · %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO if verbose else logging.WARNING)




def usage_from_raw(raw) -> dict:
    """Pull token counts off a raw AIMessage (from with_structured_output(include_raw=True)).


    Returns {} if usage isn't available (e.g. a stubbed LLM in tests, or a provider that doesn't
    report usage), so callers never have to special-case it.
    """
    um = getattr(raw, "usage_metadata", None)
    if not um:
        return {}
    return {
        "input_tokens": int(um.get("input_tokens", 0) or 0),
        "output_tokens": int(um.get("output_tokens", 0) or 0),
        "total_tokens": int(um.get("total_tokens", 0) or 0),
    }




def summarize(results: list[dict]) -> dict:
    """Aggregate per-account usage/latency across a run's result states."""
    total = {"accounts": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "latency_s": 0.0}
    for r in results:
        total["accounts"] += 1
        u = r.get("usage") or {}
        for k in ("input_tokens", "output_tokens", "total_tokens"):
            total[k] += u.get(k, 0)
        total["latency_s"] += float(r.get("latency_s") or 0.0)
    return total




# ══════════════════════════════════════════════════════════════════════════════
# CORE — models (typed data contracts for the whole pipeline)
# ══════════════════════════════════════════════════════════════════════════════


# Sentiment scores within ±this band read as NEUTRAL; outside it, the label must match the score's
# sign. Used to reconcile the two fields the LLM produces independently.
_SENTIMENT_NEUTRAL_BAND = 0.15




class Account(BaseModel):
    """Validated account record. Real data sources map onto this shape."""
    account_id: str
    name: str
    csm: str
    industry: Optional[str] = None    # telecom / utilities / energy (descriptive)
    region: Optional[str] = None      # descriptive
    stage: Optional[str] = None       # "deployment" or "live" (descriptive)
    acv_usd: int                      # annual contract value — used for $-at-risk rollup
    account_age_months: int           # for the "below 40% at 6 months" rule
    modules_licensed: int
    modules_active: int
    logins_last_30d: int
    days_since_csm_contact: int
    open_tickets: int
    days_to_renewal: int
    milestone_status: str
    recent_comms: list[str]           # raw, header-annotated documents from every source (the mess)




class Evidence(BaseModel):
    """A single verbatim citation backing an extracted claim."""
    source: str = Field(description="Where the quote is from, e.g. 'EMAIL 2026-08-03' or 'SUPPORT TKT-847'")
    quote: str = Field(description="The EXACT verbatim substring from the comms that supports the claim — never paraphrased")




class Finding(BaseModel):
    """An extracted claim that must be backed by at least one Evidence quote."""
    summary: str = Field(description="One short sentence stating the finding")
    evidence: list[Evidence] = Field(default_factory=list, description="Verbatim quote(s) that prove the finding")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="0.0-1.0 confidence this finding is real and material")




class ExtractedSignals(BaseModel):
    """
    The LLM's job in the analysis step: turn the messy multi-source comms into a STRUCTURED, CITED
    read. It extracts facts and the verbatim quotes that back them — it does NOT score or grade.
    Scoring stays deterministic (compute_health).


    The first block is consumed by the rubric; the rest is the richer analyst read. Every added
    field is optional so the deterministic golden tests can pin a minimal signal object.
    """
    # ── consumed by the deterministic rubric ──
    sentiment_score: float = Field(ge=-1.0, le=1.0, description="Overall tone of recent comms, from -1.0 (very negative) to 1.0 (very positive)")
    sentiment_label: Literal["POSITIVE", "NEUTRAL", "NEGATIVE"] = Field(description="POSITIVE, NEUTRAL, or NEGATIVE")
    key_themes: list[str] = Field(description="2-4 short phrases capturing what is driving this relationship right now")
    churn_signals: list[str] = Field(description="EXACT verbatim phrases from comms indicating churn/dissatisfaction risk (empty if none)")
    expansion_signals: list[str] = Field(description="EXACT verbatim phrases from comms indicating upsell/referral/expansion opportunity (empty if none)")


    # ── the richer, cited analyst read (all optional) ──
    sentiment_evidence: list[Evidence] = Field(default_factory=list, description="Verbatim quote(s) that justify the sentiment score")
    risks: list[Finding] = Field(default_factory=list, description="Material risks to the relationship, each with a verbatim quote")
    commitments: list[Finding] = Field(default_factory=list, description="Promises made (by us or the customer); each with a verbatim quote")
    blockers: list[Finding] = Field(default_factory=list, description="Concrete blockers to adoption/value; each with a verbatim quote")
    open_asks: list[Finding] = Field(default_factory=list, description="Outstanding requests awaiting a response; each with a verbatim quote")
    competitor_mentions: list[str] = Field(default_factory=list, description="Any mention of evaluating/comparing alternatives (EXACT verbatim phrase)")
    stakeholder_changes: list[Finding] = Field(default_factory=list, description="Champion departures, new decision-makers, or reorgs; each with a verbatim quote")
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="0.0-1.0 confidence in the overall read, given how noisy/complete the comms are")


    @model_validator(mode="after")
    def _reconcile_sentiment_label(self) -> "ExtractedSignals":
        """Snap sentiment_label to the sign of sentiment_score so the two never disagree.


        The model produces both fields independently, so it can return e.g. score +0.4 with label
        NEGATIVE. Since the score is the source of truth (it's the rubric's only LLM input), we
        deterministically derive the label from it. This never touches the score, so it cannot
        change the deterministic health score."""
        if self.sentiment_score > _SENTIMENT_NEUTRAL_BAND:
            expected = "POSITIVE"
        elif self.sentiment_score < -_SENTIMENT_NEUTRAL_BAND:
            expected = "NEGATIVE"
        else:
            expected = "NEUTRAL"
        if self.sentiment_label != expected:
            self.sentiment_label = expected
        return self




class HealthScore(BaseModel):
    """Output of the deterministic rubric. Fully reproducible and auditable."""
    score: int
    rag_status: str                   # RED / AMBER / GREEN
    adoption_pct: float
    components: dict[str, int]        # per-signal 0-100 sub-scores (glass box)
    rules_fired: list[str] = []       # which override rules changed the RAG, and why
    previous_score: Optional[int] = None
    delta: Optional[int] = None       # change vs last run (early-warning trend)




class AccountBrief(BaseModel):
    """The CSM-facing brief. brief_type is set by which branch of the graph ran."""
    brief_type: Literal["RETENTION", "STANDARD", "EXPANSION"] = Field(description="RETENTION, STANDARD, or EXPANSION")
    headline: str = Field(description="One sharp line telling the CSM exactly where this account stands")
    situation: str = Field(description="2-3 sentences of what is actually happening, referencing specific data")
    risks: list[str] = Field(description="2-3 bullets, each citing a specific number or fact")
    action: str = Field(description="The single most important, time-bound action for the CSM this week")
    draft: str = Field(description="A ready-to-review draft (customer email or internal play) the CSM can edit and send — human stays in the loop")




# ══════════════════════════════════════════════════════════════════════════════
# CORE — trend store (tiny JSON-backed memory of last run's scores → early warning)
# ══════════════════════════════════════════════════════════════════════════════
# Turns a one-time snapshot into an early-warning system: a CSM sees an account *deteriorating*
# before it hits a hard threshold. Deliberately a flat JSON file — this is a POC. Delete
# data/trend.json to reset the baseline.


_TREND_PATH = TREND_JSON


# Serialises read-modify-write so the concurrent runner (--concurrency > 1) can't interleave
# save_current() calls and lose updates or corrupt the JSON file.
_TREND_LOCK = threading.Lock()




def _trend_load() -> dict:
    if not _TREND_PATH.exists():
        return {}
    try:
        with open(_TREND_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}




def get_previous(account_id: str):
    """Return last run's score for an account, or None if we've never seen it."""
    with _TREND_LOCK:
        return _trend_load().get(account_id)




def save_current(account_id: str, score: int) -> None:
    """Persist this run's score as the new baseline for next time."""
    with _TREND_LOCK:
        data = _trend_load()
        data[account_id] = score
        _TREND_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_TREND_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)



