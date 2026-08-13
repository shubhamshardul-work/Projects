"""sources — the data-acquisition layer. Mode dispatch, the seed, the comms corpus, a resilient
REST helper, the MCP client, fixture builders, the identity crosswalk, the five source
connectors (CRM / platform / support / slack / email) and the aggregation that assembles one
validated Account. Swap any source with an env var; the intelligence layer never changes."""


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




# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER — mode dispatch
# ══════════════════════════════════════════════════════════════════════════════
# Every connector chooses its backend from an env var (e.g. CRM_MODE=csv). We read it per-call (not
# once at import) so a mode can be flipped at runtime and tests can drive it with monkeypatch.setenv.
# Everything defaults to "mock", so the default run is unchanged.


def mode(env_name: str, default: str = "mock") -> str:
    """Return the lowercased mode for a source (e.g. mode('CRM_MODE') -> 'mock' | 'csv')."""
    return (os.getenv(env_name) or default).strip().lower()




# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER — seed (shared MOCK backend)
# ══════════════════════════════════════════════════════════════════════════════
# In this POC every connector reads the same seed file (data/accounts.json) and projects only the
# fields its real system would own. In production each connector would hit its own system.


_BUNDLE = None
_SEED = None




def _bundle() -> dict:
    """Load the read-only data bundle (accounts + comms corpus + eval gold) once, cached."""
    global _BUNDLE
    if _BUNDLE is None:
        with open(SEED_JSON, "r", encoding="utf-8") as f:
            _BUNDLE = json.load(f)
    return _BUNDLE




def load_seed() -> dict:
    """Return the seed as {account_id: record}, loaded once and cached."""
    global _SEED
    if _SEED is None:
        _SEED = {r["account_id"]: r for r in _bundle()["accounts"]}
    return _SEED




def eval_gold() -> dict:
    """Hand-labelled extraction expectations per hero account (drops _comment-style keys)."""
    return {k: v for k, v in _bundle().get("gold", {}).items() if not k.startswith("_")}




def _require(account_id: str) -> dict:
    rec = load_seed().get(account_id)
    if rec is None:
        raise ValueError(f"Account '{account_id}' not found in seed data.")
    return rec




# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER — comms corpus loader (the raw, messy communications)
# ══════════════════════════════════════════════════════════════════════════════
# Real customer signal is scattered across long email threads (quoted history, signatures, noise),
# Slack, support tickets, and CRM call notes. This is the single place that loads that raw material
# so each source connector can project just its own channel.
#   • rich   → the seed bundle carries a channel-tagged markdown corpus for the account → parse it.
#   • fallback → no corpus → synthesize modest documents from the account's `recent_comms` seed field.
# A document is a dict: {channel, label, body, raw}. `raw` is the full header-annotated text the LLM
# reads (and that grounding checks quotes against).


# Channel tags used in the corpus headers and by the connectors.
EMAIL, SLACK, SUPPORT, CRM_NOTE = "EMAIL", "SLACK", "SUPPORT", "CRM_NOTE"


# Matches a section header line like:  ### [EMAIL | 2026-08-03 | ops@x → csm]
_SECTION = re.compile(
    r"^###\s*\[(?P<hdr>[^\]]*)\]\s*$(?P<body>.*?)(?=^###\s*\[|\Z)",
    re.MULTILINE | re.DOTALL,
)




def _label(header_inner: str) -> str:
    """Short citation label, e.g. 'EMAIL 2026-08-03' or 'SUPPORT TKT-847'."""
    parts = [p.strip() for p in header_inner.split("|")]
    channel = parts[0].upper()
    extra = parts[1] if len(parts) > 1 else ""
    return f"{channel} {extra}".strip()




def _parse_corpus(text: str) -> list[dict]:
    docs: list[dict] = []
    for m in _SECTION.finditer(text):
        hdr = m.group("hdr").strip()
        body = m.group("body").strip()
        channel = hdr.split("|")[0].strip().upper()
        docs.append({
            "channel": channel,
            "label": _label(hdr),
            "body": body,
            "raw": f"[{hdr}]\n{body}".strip(),
        })
    return docs




def _fallback_documents(account_id: str) -> list[dict]:
    """No rich file: build modest EMAIL/SUPPORT docs from accounts.json comms."""
    rec = _require(account_id)
    docs: list[dict] = []
    for line in rec.get("recent_comms", []):
        if line.lower().startswith("support ticket"):
            docs.append({"channel": SUPPORT, "label": SUPPORT, "body": line, "raw": f"[SUPPORT]\n{line}"})
        else:
            docs.append({"channel": EMAIL, "label": EMAIL, "body": line, "raw": f"[EMAIL]\n{line}"})
    return docs




def load_documents(account_id: str) -> list[dict]:
    """Return all raw documents for an account (rich corpus from the bundle if present, else fallback)."""
    text = _bundle().get("comms", {}).get(account_id)
    if text:
        return _parse_corpus(text)
    return _fallback_documents(account_id)




def texts_for(account_id: str, channel: str) -> list[str]:
    """The raw text of every document on one channel (what a connector returns)."""
    return [d["raw"] for d in load_documents(account_id) if d["channel"] == channel]




# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER — resilient JSON-over-HTTP GET (stdlib only; used by the GitHub connector)
# ══════════════════════════════════════════════════════════════════════════════
# Real source APIs fail transiently and rate-limit. This adds retries with exponential backoff,
# honours Retry-After, and turns an exhausted rate limit into a clear, actionable error. Kept
# dependency-free (urllib). Tests monkeypatch `get_json`, so no real network call is made offline.


DEFAULT_HEADERS = {"User-Agent": "fieldora-cs-intelligence"}




def get_json(url: str, headers: dict | None = None, timeout: float = 15.0,
             retries: int = 3, backoff: float = 1.5) -> object:
    """GET `url` and parse JSON, retrying transient failures (5xx / network / rate-limit).


    Raises RuntimeError with a clear message on an exhausted rate limit or after all retries.
    Non-retryable HTTP errors (e.g. 404) are raised as-is.
    """
    merged = {**DEFAULT_HEADERS, **(headers or {})}
    last_err: Exception | None = None


    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=merged)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (403, 429):                       # rate limited / throttled
                if e.headers.get("X-RateLimit-Remaining") == "0":
                    raise RuntimeError(
                        "API rate limit exhausted. Set an auth token (e.g. GITHUB_TOKEN) "
                        "or retry later."
                    ) from e
                wait = _retry_after_seconds(e.headers.get("Retry-After"), backoff * (2 ** attempt))
            elif 500 <= e.code < 600:                      # transient server error
                wait = backoff * (2 ** attempt)
            else:
                raise                                      # 4xx (not throttling) → caller handles
        except urllib.error.URLError as e:                 # DNS / connection / timeout
            last_err = e
            wait = backoff * (2 ** attempt)


        if attempt < retries - 1:                          # don't sleep before giving up
            logger.info(f"_net: retrying {url} in {min(wait, 10.0):.1f}s")
            time.sleep(min(wait, 10.0))


    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last_err}")




def _retry_after_seconds(value: str | None, fallback: float) -> float:
    """Parse a Retry-After header (numeric seconds; HTTP-date form falls back to backoff)."""
    if not value:
        return fallback
    try:
        return float(value)
    except ValueError:
        return fallback                                    # HTTP-date form — just back off




# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER — MCP client helper (shared by the Slack/Gmail connectors)
# ══════════════════════════════════════════════════════════════════════════════
# MCP is the agent-native way to reach a source system: a server wraps the system and exposes tools
# (slack_get_channel_history, search_emails, …); we load those tools and call them. `with_tools()`
# opens ONE session so a later call can depend on an earlier one (Slack: list-channels → resolve id
# → get-history). `langchain-mcp-adapters` is an OPTIONAL extra, imported lazily inside the call.
# This path is CODE-COMPLETE but not runtime-verified here (needs the extra + a running server +
# credentials).


def server_config(prefix: str) -> dict:
    """Build a MultiServerMCPClient server config from env for a given prefix (e.g. 'SLACK').


    stdio (local subprocess):  {PREFIX}_MCP_COMMAND="npx -y @modelcontextprotocol/server-slack"
    http/sse (remote server):  {PREFIX}_MCP_URL="http://localhost:3001/sse"
    Extra env for the server (tokens) is passed through the {PREFIX}_MCP_ENV allow-list.
    """
    url = os.getenv(f"{prefix}_MCP_URL")
    if url:
        return {"url": url, "transport": "sse"}


    command = os.getenv(f"{prefix}_MCP_COMMAND")
    if not command:
        raise RuntimeError(
            f"{prefix} MCP not configured. Set {prefix}_MCP_COMMAND (stdio) or {prefix}_MCP_URL "
            f"(sse), plus the server's credentials, then set the source's *_MODE=mcp."
        )
    argv = shlex.split(command)
    passthrough = [k.strip() for k in os.getenv(f"{prefix}_MCP_ENV", "").split(",") if k.strip()]
    env = {k: os.environ[k] for k in passthrough if k in os.environ}
    return {"command": argv[0], "args": argv[1:], "transport": "stdio", "env": env or None}




def with_tools(prefix: str, run):
    """Open ONE MCP session for `prefix`, load its tools, and invoke `run(tools)` inside it.


    `run` is an async callable receiving `{tool_name: tool}` and returning the connector's result;
    keeping the whole sequence in one session lets a later call depend on an earlier one. Raises a
    clear, actionable error if the optional adapter isn't installed."""
    try:
        import langchain_mcp_adapters  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "MCP support not installed. Install the extra:  pip install "
            "'fieldora-cs-intelligence[mcp]'  (adds langchain-mcp-adapters), then run the MCP server."
        ) from e
    return asyncio.run(_run_session(prefix, run))




async def _run_session(prefix: str, run):
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.tools import load_mcp_tools


    name = prefix.lower()
    client = MultiServerMCPClient({name: server_config(prefix)})
    async with client.session(name) as session:          # one connection for the whole sequence
        tools = {t.name: t for t in await load_mcp_tools(session)}
        return await run(tools)




def require(tools: dict, name: str):
    """Fetch a tool by name from a loaded set, with a helpful error listing what's available."""
    tool = tools.get(name)
    if tool is None:
        raise RuntimeError(f"MCP tool '{name}' not found on the server. Available: "
                           f"{', '.join(sorted(tools)) or '(none)'}")
    return tool




# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER — fixtures (build the local "landing" data the cred-free live modes read)
# ══════════════════════════════════════════════════════════════════════════════
# Fieldora is fictional, so there is no real CRM/warehouse/mailbox. To make the live modes actually
# runnable (and reproducible, nothing binary committed), we generate realistic source artifacts from
# the bundled seed + comms. Each ensure_* builds on first use if the file is missing.


# Column contracts for the file/db fixtures. These mirror the mock projections in _CRM_FIELDS /
# _PLATFORM_FIELDS (kept explicit here); they are stable schemas.
CRM_COLUMNS = ["account_id", "name", "csm", "industry", "region", "stage",
               "acv_usd", "account_age_months", "days_to_renewal", "days_since_csm_contact"]
CRM_NUMERIC = {"acv_usd", "account_age_months", "days_to_renewal", "days_since_csm_contact"}


USAGE_COLUMNS = ["account_id", "modules_licensed", "modules_active", "logins_last_30d", "milestone_status"]
USAGE_NUMERIC = {"modules_licensed", "modules_active", "logins_last_30d"}


CROSSWALK_COLUMNS = ["account_id", "slack_channel", "gmail_query", "github_repo"]


_PLACEHOLDER_DATE = "2026-08-01"   # deterministic date for comms docs that carry none




def _slug(name: str) -> str:
    return name.lower().replace(" ", "-")




def _domain_for(account_id: str) -> str:
    """Best-effort customer email domain for an account (for the gmail query / crosswalk)."""
    for doc in load_documents(account_id):
        if doc["channel"] == EMAIL and "@" in doc["raw"]:
            # first address that isn't ours
            for token in doc["raw"].replace("<", " ").replace(">", " ").split():
                if "@" in token and "fieldora.com" not in token:
                    return token.split("@")[-1].strip(" |>].")
    return f"{_slug(_require(account_id)['name'])}.example"




# ── CRM CSV ─────────────────────────────────────────────────────────────────


def build_crm_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CRM_COLUMNS)
        w.writeheader()
        for aid, rec in load_seed().items():
            w.writerow({"account_id": aid, **{c: rec[c] for c in CRM_COLUMNS if c != "account_id"}})
    return path




def ensure_crm_csv(path: Path) -> Path:
    return path if path.exists() else build_crm_csv(path)




# ── Platform usage SQLite ─────────────────────────────────────────────────────


def build_usage_db(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    try:
        con.execute(
            "CREATE TABLE account_usage ("
            "account_id TEXT PRIMARY KEY, modules_licensed INTEGER, modules_active INTEGER, "
            "logins_last_30d INTEGER, milestone_status TEXT)"
        )
        con.executemany(
            "INSERT INTO account_usage VALUES (?, ?, ?, ?, ?)",
            [(aid, r["modules_licensed"], r["modules_active"], r["logins_last_30d"], r["milestone_status"])
             for aid, r in load_seed().items()],
        )
        con.commit()
    finally:
        con.close()
    return path




def ensure_usage_db(path: Path) -> Path:
    return path if path.exists() else build_usage_db(path)




# ── Email .eml files ──────────────────────────────────────────────────────────


def _doc_to_eml(raw: str) -> EmailMessage:
    """Turn a corpus EMAIL document ('[EMAIL | date | from → to]\\nSubject: …\\n\\nbody') into a
    real RFC-822 message, so the email connector can parse it back like a live mailbox export."""
    header, _, rest = raw.partition("\n")
    inner = header.strip().lstrip("[").rstrip("]")
    parts = [p.strip() for p in inner.split("|")]
    dt_str = parts[1] if len(parts) > 1 and parts[1][:4].isdigit() else _PLACEHOLDER_DATE
    if len(parts) > 2 and "→" in parts[2]:
        frm, to = (s.strip() for s in parts[2].split("→", 1))
    else:
        frm, to = "customer@example.com", "csm@fieldora.com"


    subject, body = "(imported)", rest
    if rest.lstrip().lower().startswith("subject:"):
        first, _, after = rest.lstrip().partition("\n")
        subject = first.split(":", 1)[1].strip()
        body = after.lstrip("\n")


    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = frm, to, subject
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        dt = datetime.strptime(_PLACEHOLDER_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    msg["Date"] = format_datetime(dt)
    msg.set_content(body or "(no body)")
    return msg




def build_email_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for aid in load_seed():
        emails = [d for d in load_documents(aid) if d["channel"] == EMAIL]
        if not emails:
            continue
        acc_dir = root / aid
        acc_dir.mkdir(parents=True, exist_ok=True)
        for i, doc in enumerate(emails, 1):
            (acc_dir / f"{i:02d}.eml").write_bytes(_doc_to_eml(doc["raw"]).as_bytes())
    return root




def ensure_email_dir(root: Path) -> Path:
    return root if root.exists() else build_email_dir(root)




# ── Identity crosswalk file ───────────────────────────────────────────────────


def build_crosswalk_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CROSSWALK_COLUMNS)
        w.writeheader()
        for aid, rec in load_seed().items():
            domain = _domain_for(aid)
            w.writerow({
                "account_id": aid,
                "slack_channel": f"#cs-{_slug(rec['name'])}",
                "gmail_query": f"from:{domain} OR to:{domain}",
                "github_repo": "",     # user maps a public repo per account, or sets GITHUB_REPO
            })
    return path




def ensure_crosswalk_csv(path: Path) -> Path:
    return path if path.exists() else build_crosswalk_csv(path)




def build_all() -> None:
    """Regenerate every fixture (used by `python -m fieldora --build-fixtures`)."""
    build_crm_csv(LIVE_DIR / "crm.csv")
    build_usage_db(LIVE_DIR / "fieldora.db")
    build_email_dir(LIVE_DIR / "email")
    build_crosswalk_csv(LIVE_DIR / "crosswalk.csv")




# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER — crosswalk (identity resolution across source systems)
# ══════════════════════════════════════════════════════════════════════════════
# One account is a CSV row here, a Slack channel there, a Gmail thread and a GitHub repo elsewhere.
# This is the crosswalk: account_id → {slack_channel, gmail_query, github_repo}. A deterministic
# mapping table (data/live/crosswalk.csv) with a derived fallback for any account not yet mapped.


CROSSWALK_CSV = LIVE_DIR / "crosswalk.csv"




@lru_cache(maxsize=1)
def _crosswalk_table() -> dict:
    """Load crosswalk.csv as {account_id: row}, building it from the seed if missing.


    Reads the module-level CROSSWALK_CSV (not a bound default) so tests can point it elsewhere;
    cached, so call `_crosswalk_table.cache_clear()` after repointing."""
    ensure_crosswalk_csv(CROSSWALK_CSV)
    with open(CROSSWALK_CSV, newline="", encoding="utf-8") as f:
        return {r["account_id"]: r for r in csv.DictReader(f)}




def _crosswalk_derived(account_id: str) -> dict:
    """Fallback identity when an account isn't in (or has blanks in) the crosswalk."""
    name = _require(account_id)["name"]
    domain = _domain_for(account_id)
    return {
        "slack_channel": f"#cs-{name.lower().replace(' ', '-')}",
        "gmail_query": f"from:{domain} OR to:{domain}",
        "github_repo": "",
    }




def crosswalk_get(account_id: str) -> dict:
    """Resolve an account's per-source keys, falling back to derivation for any missing field."""
    row = _crosswalk_table().get(account_id, {})
    derived = _crosswalk_derived(account_id)
    return {k: (row.get(k) or derived[k]) for k in ("slack_channel", "gmail_query", "github_repo")}




# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER — CRM connector (identity + commercial terms; system of record)
# ══════════════════════════════════════════════════════════════════════════════
# Real system: Salesforce / HubSpot. Here: mock (seed) or a CSV export.
#   CRM_MODE  mock (default) → seed  |  csv → data/live/crm.csv (built from the seed on first use)


CRM_CSV = LIVE_DIR / "crm.csv"


_CRM_FIELDS = ["name", "csm", "industry", "region", "stage",
               "acv_usd", "account_age_months", "days_to_renewal",
               "days_since_csm_contact"]




def crm_list_accounts() -> list[dict]:
    """Return the portfolio (the CRM is the source of truth for which accounts exist)."""
    if mode("CRM_MODE") == "csv":
        return _list_csv()
    return [{"account_id": aid, "name": r["name"], "csm": r["csm"]}
            for aid, r in load_seed().items()]




def crm_get_account(account_id: str) -> dict:
    """Return identity + commercial fields for one account."""
    if mode("CRM_MODE") == "csv":
        return _get_csv(account_id)
    r = _require(account_id)
    return {"account_id": account_id, **{k: r[k] for k in _CRM_FIELDS}}




def get_notes(account_id: str) -> list[str]:
    """Return CRM activity notes / call logs for an account (a comms source).


    Identity and call-logs are different artifacts: live notes would come from the CRM's activity
    API. In this POC notes always read from the comms corpus, independent of CRM_MODE.
    """
    return texts_for(account_id, CRM_NOTE)




def _cast(row: dict) -> dict:
    """Coerce numeric CRM columns from CSV strings to int; leave the rest as-is."""
    return {k: (int(v) if k in CRM_NUMERIC and v not in (None, "") else v)
            for k, v in row.items()}




def _rows(path=None) -> list[dict]:
    path = path or CRM_CSV                 # resolve the module global at call time (test-friendly)
    ensure_crm_csv(path)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))




def _list_csv(path=None) -> list[dict]:
    return [{"account_id": r["account_id"], "name": r["name"], "csm": r["csm"]} for r in _rows(path)]




def _get_csv(account_id: str, path=None) -> dict:
    path = path or CRM_CSV
    for r in _rows(path):
        if r["account_id"] == account_id:
            return _cast(r)
    raise ValueError(f"Account '{account_id}' not found in CRM export {path}.")




# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER — platform connector (Fieldora product-usage data)
# ══════════════════════════════════════════════════════════════════════════════
# Real system: the product's usage API or an analytics warehouse (Snowflake/BigQuery).
#   PLATFORM_MODE  mock (default) → seed  |  sqlite → a real, parametrized SQL read against
#   data/live/fieldora.db (built from the seed on first use).


USAGE_DB = LIVE_DIR / "fieldora.db"


_PLATFORM_FIELDS = ["modules_licensed", "modules_active", "logins_last_30d", "milestone_status"]




def get_usage(account_id: str) -> dict:
    """Return product-usage signals for one account."""
    if mode("PLATFORM_MODE") == "sqlite":
        return _get_sqlite(account_id)
    r = _require(account_id)
    return {k: r[k] for k in _PLATFORM_FIELDS}




def _get_sqlite(account_id: str, path=None) -> dict:
    path = path or USAGE_DB                                   # resolve global at call time
    ensure_usage_db(path)
    # Build a proper file URI (handles Windows paths + spaces) and open read-only.
    con = sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(
            f"SELECT {', '.join(_PLATFORM_FIELDS)} FROM account_usage WHERE account_id = ?",
            (account_id,),                                    # parametrized — no injection
        )
        row = cur.fetchone()
    finally:
        con.close()
    if row is None:
        raise ValueError(f"Account '{account_id}' not found in usage warehouse {path}.")
    return {k: row[k] for k in _PLATFORM_FIELDS}




# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER — support connector (open support tickets)
# ══════════════════════════════════════════════════════════════════════════════
# Real system: Zendesk / Jira. Here: mock (seed) or GitHub Issues (issues ARE tickets).
#   SUPPORT_MODE  mock (default) → corpus + seed count  |  github → public repo Issues via REST
#   (repo comes from the crosswalk or GITHUB_REPO; optional GITHUB_TOKEN raises the rate limit).


_GITHUB_API = "https://api.github.com"




def support_get_messages(account_id: str) -> list[str]:
    """Return the open support tickets for an account as raw documents."""
    if mode("SUPPORT_MODE") == "github":
        return _get_github(account_id)
    return texts_for(account_id, SUPPORT)




def get_open_ticket_count(account_id: str) -> int:
    """How many tickets are open (drives the friction score)."""
    if mode("SUPPORT_MODE") == "github":
        return len(_get_github(account_id))   # shares the cached fetch with support_get_messages
    return _require(account_id)["open_tickets"]




def _repo(account_id: str) -> str:
    """owner/repo for this account, from the crosswalk or the GITHUB_REPO fallback."""
    return crosswalk_get(account_id).get("github_repo") or os.getenv("GITHUB_REPO", "")




def _get_github(account_id: str) -> list[str]:
    repo = _repo(account_id)
    if not repo:
        return []   # no repo mapped → no tickets (graceful, not an error; no fetch)
    return list(_fetch_issues(repo))   # cached tuple → fresh list for safe concatenation




@lru_cache(maxsize=64)
def _fetch_issues(repo: str) -> tuple[str, ...]:
    """Fetch a repo's open issues as ticket documents. Cached per repo so support_get_messages and
    get_open_ticket_count share ONE call within a run. Returns a tuple so the cached value can't be
    mutated by a caller."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"


    url = f"{_GITHUB_API}/repos/{repo}/issues?state=open&per_page=50"
    issues = get_json(url, headers=headers)


    docs = []
    for it in issues:
        if "pull_request" in it:      # the issues endpoint also returns PRs — skip them
            continue
        title = (it.get("title") or "").strip()
        body = (it.get("body") or "").strip()
        docs.append(f"[SUPPORT | #{it.get('number')} | {it.get('state')}]\nSubject: {title}\n{body}")
    return tuple(docs)




# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER — Slack connector (internal CS-team channel notes)
# ══════════════════════════════════════════════════════════════════════════════
# Real system: Slack. Here: mock (corpus, with a synthesized fallback) or Slack via MCP.
#   SLACK_MODE  mock (default) → corpus SLACK docs, else a synthesized note  |  mcp → real Slack


def slack_get_messages(account_id: str) -> list[str]:
    """Return recent internal Slack messages for an account's channel."""
    if mode("SLACK_MODE") == "mcp":
        return _get_slack_mcp(account_id)
    docs = texts_for(account_id, SLACK)
    return docs if docs else [_synth_note(account_id)]




def _synth_note(account_id: str) -> str:
    r = _require(account_id)
    adoption = r["modules_active"] / max(r["modules_licensed"], 1)


    if r["days_to_renewal"] < 90 and (adoption < 0.40 or r["open_tickets"] > 2):
        note = (f"@here heads-up on {r['name']}: renewal in {r['days_to_renewal']}d, "
                f"adoption ~{adoption:.0%}, {r['open_tickets']} open tickets — needs a plan.")
    elif adoption >= 0.80 and r["open_tickets"] <= 1:
        note = f"{r['name']} looking strong ({adoption:.0%} adoption) — good expansion candidate."
    else:
        note = (f"{r['name']}: steady. Adoption ~{adoption:.0%}, "
                f"{r['days_since_csm_contact']}d since last contact — keeping an eye on it.")


    channel = f"#cs-{r['name'].lower().replace(' ', '-')}"
    return f"[SLACK | {channel}]\n{note}"




def _get_slack_mcp(account_id: str) -> list[str]:
    channel_name = crosswalk_get(account_id)["slack_channel"].lstrip("#")


    async def _run(tools):
        # Tool names match the reference Slack MCP server; confirm against the server you run.
        # list channels → resolve the id → read that channel's history, all in one session.
        channels = await require(tools, "slack_list_channels").ainvoke({})
        channel_id = _find_channel_id(channels, channel_name)
        if not channel_id:
            return []
        history = await require(tools, "slack_get_channel_history").ainvoke(
            {"channel_id": channel_id, "limit": 20}
        )
        return _history_to_docs(history, channel_name)


    return with_tools("SLACK", _run)




def _find_channel_id(channels, name: str) -> str | None:
    items = channels.get("channels", channels) if isinstance(channels, dict) else channels
    if not isinstance(items, list):
        return None
    for ch in items:
        if isinstance(ch, dict) and ch.get("name", "").lstrip("#") == name:
            return ch.get("id")
    return None




def _history_to_docs(history, channel_name: str) -> list[str]:
    msgs = history.get("messages", history) if isinstance(history, dict) else history
    if not isinstance(msgs, list):
        return [f"[SLACK | #{channel_name}]\n{msgs}"]
    docs = []
    for m in msgs:
        text = m.get("text", "") if isinstance(m, dict) else str(m)
        if text.strip():
            docs.append(f"[SLACK | #{channel_name}]\n{text.strip()}")
    return docs




# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER — email connector (customer/CSM correspondence; the main sentiment source)
# ══════════════════════════════════════════════════════════════════════════════
# Real system: Gmail / Outlook. Here: mock (seed), local .eml files, or Gmail via MCP.
#   EMAIL_MODE  mock (default) → corpus  |  eml → parse data/live/email/<ACC>/*.eml  |  mcp → Gmail


EMAIL_DIR = LIVE_DIR / "email"




def email_get_messages(account_id: str) -> list[str]:
    """Return recent customer/CSM email documents for an account."""
    m = mode("EMAIL_MODE")
    if m == "eml":
        return _get_eml(account_id)
    if m == "mcp":
        return _get_gmail_mcp(account_id)
    return texts_for(account_id, EMAIL)




def _eml_to_doc(raw_bytes: bytes) -> str:
    """Parse one .eml into the same '[EMAIL | date | from → to]\\nSubject: …\\n\\nbody' shape the
    rest of the pipeline expects, so extraction/grounding behave identically to mock mode."""
    msg = BytesParser(policy=_default_policy).parsebytes(raw_bytes)
    try:
        dt = parsedate_to_datetime(msg["Date"]).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        dt = ""
    frm, to, subject = msg["From"] or "", msg["To"] or "", msg["Subject"] or ""
    body_part = msg.get_body(preferencelist=("plain",))
    body = body_part.get_content().strip() if body_part else (msg.get_content() or "").strip()
    return f"[EMAIL | {dt} | {frm} → {to}]\nSubject: {subject}\n\n{body}".strip()




def _get_eml(account_id: str, root=None) -> list[str]:
    root = root or EMAIL_DIR               # resolve global at call time (test-friendly)
    ensure_email_dir(root)
    acc_dir = root / account_id
    if not acc_dir.exists():
        return []
    return [_eml_to_doc(p.read_bytes()) for p in sorted(acc_dir.glob("*.eml"))]




def _get_gmail_mcp(account_id: str) -> list[str]:
    query = crosswalk_get(account_id)["gmail_query"]


    async def _run(tools):
        # Tool names match community Gmail MCP servers; confirm against the server you run.
        results = await require(tools, "search_emails").ainvoke({"query": query, "max_results": 10})
        return _gmail_results_to_docs(results)


    return with_tools("GMAIL", _run)




def _gmail_results_to_docs(results) -> list[str]:
    """Best-effort map of a Gmail MCP tool result into EMAIL docs. MCP tools return provider-shaped
    payloads (often a list of message dicts, or a text block); handle the common shapes."""
    messages = results.get("messages", results) if isinstance(results, dict) else results
    if not isinstance(messages, list):
        return [str(messages)]
    docs = []
    for m in messages:
        if not isinstance(m, dict):
            docs.append(str(m))
            continue
        dt = m.get("date") or m.get("internalDate") or ""
        frm, to, subj = m.get("from", ""), m.get("to", ""), m.get("subject", "")
        body = m.get("body") or m.get("snippet") or ""
        docs.append(f"[EMAIL | {dt} | {frm} → {to}]\nSubject: {subj}\n\n{body}".strip())
    return docs




# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER — aggregation (fan out to every source, assemble one typed Account)
# ══════════════════════════════════════════════════════════════════════════════
# This is what the agent talks to; it never knows whether each field came from a mock fixture or a
# live system.


def _safe_comms(fetch, source: str) -> list[str]:
    """Fetch one COMMS (text) source, tolerating an outage. A qualitative source being down should
    degrade the read, not fail the account — we log it and continue. (Scoring inputs like the CRM
    identity, platform usage, and support ticket COUNT stay hard dependencies below: we won't
    fabricate a number the health score depends on.)"""
    try:
        return fetch()
    except Exception as e:  # noqa: BLE001 — any source-specific failure degrades gracefully
        logger.warning(f"comms source '{source}' unavailable for this account: {e}")
        return []




def list_accounts() -> list[dict]:
    """The portfolio index (from the CRM)."""
    return crm_list_accounts()




def get_account(account_id: str) -> Account:
    """Pull from every source and assemble a validated Account."""
    crm = crm_get_account(account_id)
    usage = get_usage(account_id)
    # The messy, multi-source dump the extraction step has to make sense of: customer email,
    # internal Slack, support tickets, and CRM call notes. Each text source degrades gracefully
    # (a down source is skipped, not fatal) — see _safe_comms.
    comms = (
        _safe_comms(lambda: email_get_messages(account_id), "email")
        + _safe_comms(lambda: slack_get_messages(account_id), "slack")
        + _safe_comms(lambda: support_get_messages(account_id), "support")
        + _safe_comms(lambda: get_notes(account_id), "crm_notes")
    )


    return Account(
        account_id=account_id,
        # ── from CRM ──
        name=crm["name"],
        csm=crm["csm"],
        industry=crm["industry"],
        region=crm["region"],
        stage=crm["stage"],
        acv_usd=crm["acv_usd"],
        account_age_months=crm["account_age_months"],
        days_to_renewal=crm["days_to_renewal"],
        days_since_csm_contact=crm["days_since_csm_contact"],
        # ── from Platform ──
        modules_licensed=usage["modules_licensed"],
        modules_active=usage["modules_active"],
        logins_last_30d=usage["logins_last_30d"],
        milestone_status=usage["milestone_status"],
        # ── from Support ──
        open_tickets=get_open_ticket_count(account_id),
        # ── from Email + Slack ──
        recent_comms=comms,
    )