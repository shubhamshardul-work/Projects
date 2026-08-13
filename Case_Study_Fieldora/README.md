# Fieldora — CSM Account Intelligence

A hybrid (deterministic + LLM) **account-health engine** and **weekly-brief
generator** for a Customer Success team, orchestrated with **LangGraph**.

The health score is computed by a transparent Python **rubric** — reproducible,
auditable, and tunable in one place. The **LLM** is used only for what code can't
do: reading sentiment from unstructured comms and writing the CSM-facing brief.
For each account the pipeline scores health, branches by risk (RED / AMBER /
GREEN), drafts the matching play, and rolls the whole book up for leadership with
dollars-at-risk against the GRR budget.

> **This is the case-study artifact** — the same system as `Case_Study_Codebase/`, consolidated
> from ~30 modules into a compact, layered **`fieldora/` package** plus `app.py` and `tests.py`:
>
> | File                                       | What it is                                                                                                                           |
> | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
> | **`fieldora/core.py`**                     | foundational layer — paths, config (the rubric), observability, the Pydantic models, trend memory                                    |
> | **`fieldora/sources.py`**                  | the data-acquisition layer — mode dispatch, seed, comms corpus, REST, MCP, fixtures, crosswalk, the 5 source connectors, aggregation |
> | **`fieldora/agent.py`**                    | the intelligence layer — LLM factory, prompts, extraction, grounding gate, rubric, the LangGraph pipeline, evals                     |
> | **`fieldora/cli.py`**                      | presenter (pure view helpers), the Markdown leadership report, and the argparse CLI runner                                           |
> | **`fieldora/__init__.py` · `__main__.py`** | re-export the public API (so `import fieldora` keeps working) and enable `python -m fieldora`                                        |
> | **`app.py`**                               | the Streamlit dashboard (Altair charts + shell) — imports `fieldora`                                                                 |
> | **`tests.py`**                             | the whole offline test suite (`pytest tests.py`)                                                                                     |
>
> The written deliverables (problem framing, backlog, architecture, demo script)
> are merged into [`docs/CASE_STUDY.md`](docs/CASE_STUDY.md).

---

## Quick start

```bash
# 1. Install (editable) — or use requirements.txt
pip install -e ".[all,dev]"        # all LLM providers + pytest
#   or:  pip install -r requirements.txt


# 2. Configure a provider + key
cp .env.example .env               # set LLM_PROVIDER and the matching API key


# 3. Run
python -m fieldora                 # full portfolio + leadership rollup
python -m fieldora ACC-003         # a single account (NovaPower — override + trend)
python -m fieldora ACC-003 --raw   # ...also dump the raw source comms (the mess)
python -m fieldora --report        # full run + write reports/weekly_cs_report.md


# 4. Test (no API key needed — the rubric + grounding gate are deterministic)
python -m fieldora --evals         # the eval loop (rubric golden set + optional LLM check)
pytest                             # the same golden set + full offline suite (tests.py)
```

`python -m fieldora ...` works too. After `pip install -e .`, the console script
`fieldora` is equivalent to `python -m fieldora`.

All data is synthetic and read through a connector layer, so it runs anywhere with
no credentials for the deterministic paths. Only the LLM steps (`extract_signals`,
the brief writers) need a key.

### Dashboard (Streamlit UI)

```bash
pip install -e ".[ui]"                     # adds streamlit (brings altair + pandas)
python -m fieldora --build-snapshots       # pre-run once → data/snapshots/ (calls the model)
streamlit run app.py                       # open the dashboard
```

The UI has two modes: **Replay** (default) renders the saved snapshots instantly with **no model
calls** — safe for a demo; **Live** analyzes a chosen account on demand (one model call, ~10s) and
lets you flip each data source (mock ↔ csv/sqlite/eml/github/mcp) from the sidebar. Tabs: Portfolio
rollup · per-Account (raw comms → cited extraction → grounding → score → brief) · Evals · How it works.

_(This edition ships `data/snapshots.json` already populated for all 30 accounts, so Replay works out
of the box without running `--build-snapshots` first.)_

---

## How it works

```
data/seed.json    (30-account portfolio + hero comms corpus + eval gold, one bundle)
        │
        ▼   load_account
CRM · Platform · Support · Slack · Email  ──► get_account() ──► Account
        │
        ▼   LangGraph pipeline  (the LLM's only jobs: read comms, write briefs)
extract_signals ─► verify_signals ─► score_account ─► route_by_status ─┬─ RED   → escalation_brief
 (LLM → cited      (grounding GATE:   (rubric + trend)  (conditional)   ├─ AMBER → standard_brief
  structured read)  strip ungrounded                                   └─ GREEN → expansion_brief
                    citations; re-ask ↺)
        │
        ▼
per-account brief + draft · portfolio rollup ($-at-risk vs GRR) · digest · token usage
```

**The one design decision that matters — the rubric scores, the LLM never does.**
The LLM only reads unstructured comms into a _cited_ structured read and writes the
brief; **even the milestone count is parsed deterministically** from the platform's
status string. Every extracted citation is then verified verbatim against the source
(the grounding gate) before it can reach the score or the CSM. So the RAG status is
reproducible and every claim has a receipt.

---

## Project structure

```
Case_Study_Fieldora/
├── README.md                 you are here
├── pyproject.toml            packaging + console script + pytest config
├── requirements.txt
├── .env.example              copy to .env, add a provider key
├── .gitignore
├── .streamlit/config.toml    dashboard theme (light + teal)
│
├── fieldora/                 THE ENGINE — a layered package:
│   ├── __init__.py           re-exports the public API (import fieldora) + main entry point
│   ├── __main__.py           enables `python -m fieldora`
│   ├── core.py               paths · config (rubric) · observability · models · trend
│   ├── sources.py            mode · seed · comms · REST · MCP · fixtures · crosswalk
│   │                         · CRM/platform/support/slack/email connectors · aggregation
│   ├── agent.py              llm factory · prompts · extraction · grounding · rubric · LangGraph agent · evals
│   └── cli.py                presenter (pure view helpers) · Markdown report · argparse runner + rollup
├── app.py                    Streamlit dashboard (Altair charts + shell); `streamlit run app.py`
├── tests.py                  full offline test suite; `pytest tests.py`
│
├── data/                     just two files (everything else here is generated on demand)
│   ├── seed.json             read-only source: 30-account portfolio + hero comms corpus + eval gold labels
│   └── snapshots.json        pre-built pipeline runs for the UI's Replay mode (one bundle, all 30 accounts)
│     ↳ generated, not shipped: data/live/* (cred-free fixtures — rebuilt by --build-fixtures or on first
│       use) and data/trend.json (week-over-week score memory — recreated on the next scored run)
├── reports/                  generated digests (created by --report)
└── docs/CASE_STUDY.md        the written deliverables (framing · backlog · architecture · demo)
```

---

## Configuration

Everything swappable lives in `.env` (provider + keys + data-source modes) and the
config block in `fieldora/core.py` (rubric weights and thresholds — the shared
definition of health). No behaviour change requires touching the pipeline code.

### Flip a source from mock to a real backend

Each connector picks its backend from a `*_MODE` env var — **all default to `mock`**, so the
default run needs no credentials. The `csv` / `sqlite` / `eml` / `github` backends run cred-free
(fixtures build themselves from the seed on first use); the `mcp` backends need `pip install
'.[mcp]'` + a running MCP server + credentials.

| Source         | Env flag        | Backends                                              |   Cred-free?   |
| -------------- | --------------- | ----------------------------------------------------- | :------------: |
| CRM            | `CRM_MODE`      | `mock` · `csv` (`data/live/crm.csv`)                  |       ✅       |
| Platform usage | `PLATFORM_MODE` | `mock` · `sqlite` (`data/live/fieldora.db`, real SQL) |       ✅       |
| Support        | `SUPPORT_MODE`  | `mock` · `github` (public Issues via REST)            |  ✅ (online)   |
| Email          | `EMAIL_MODE`    | `mock` · `eml` (`.eml` files) · `mcp` (Gmail)         | ✅ eml / ⚙ mcp |
| Slack          | `SLACK_MODE`    | `mock` · `mcp` (Slack)                                |     ⚙ mcp      |

```bash
# demo real acquisition — same output, sourced from a CSV + a SQL DB + real .eml files:
CRM_MODE=csv PLATFORM_MODE=sqlite EMAIL_MODE=eml python -m fieldora ACC-003
python -m fieldora --build-fixtures       # (optional) regenerate the fixtures explicitly
```

---

## Extending it

1. **Flip a source to a real backend** — set its `*_MODE` (table above). To add a new backend,
   implement one `_get_<backend>()` in that connector section and dispatch on the mode.
2. **Add a new source** — add its fetch functions + a mode dispatch in the DATA LAYER, then map its
   fields in `get_account()`.
3. **Wire a live MCP/SaaS source** — install `.[mcp]`, run the server, set `SLACK_MODE=mcp`
   (or `EMAIL_MODE=mcp`) + the `*_MCP_COMMAND`/token env vars; map account→source keys in the
   crosswalk (the `crosswalk_get` / `build_crosswalk_csv` helpers).
4. **Tune the health definition** — edit weights/thresholds in the config block of
   `fieldora/core.py`, then run `pytest` (or `python -m fieldora --evals`) to confirm the golden
   set holds.
