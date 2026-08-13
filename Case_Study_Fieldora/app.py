"""
app.py — the Streamlit dashboard.  Run with:  streamlit run app.py


Thin by design: all pipeline logic + the pure presenter helpers live in the fieldora package; this file adds
only the Altair chart builders and the Streamlit shell. The model is called ONLY in the Analyze
button handler (never on a rerun), and results live in st.session_state. Replay renders saved
snapshots with zero model calls. The layout is a narrated dashboard — a leadership Portfolio and a
per-account vertical story (banner → the mess → the cited read → the score → the play).


Palette note (dataviz method): RAG is a *status* palette (reserved colours + icon + label);
magnitude bars (component sub-scores, $-at-risk) use ONE hue and encode value by length.
"""


import os


import altair as alt
import pandas as pd
import streamlit as st


import fieldora as fx


_MODE_KEYS = ["CRM_MODE", "PLATFORM_MODE", "SUPPORT_MODE", "EMAIL_MODE", "SLACK_MODE"]
_VIEWS = ["Portfolio", "Account", "Evals", "How it works"]


st.set_page_config(page_title="Fieldora CS Intelligence", page_icon="📊", layout="wide")




# ══════════════════════════════════════════════════════════════════════════════
# Charts (Altair — ships with Streamlit, so no extra dependency)
# ══════════════════════════════════════════════════════════════════════════════


_AXIS = alt.Axis(labelColor=fx.NEUTRAL_INK, titleColor=fx.NEUTRAL_INK,
                 tickColor="#D6DBDF", domainColor="#D6DBDF", gridColor="#EEF1F3")




def component_bars(rows: list[dict]) -> alt.Chart:
    """Six health sub-scores as horizontal magnitude bars (0-100), one hue, direct value labels."""
    df = pd.DataFrame(rows)
    order = [r["component"] for r in rows]
    base = alt.Chart(df).encode(
        y=alt.Y("component:N", sort=order, title=None, axis=_AXIS),
        x=alt.X("score:Q", scale=alt.Scale(domain=[0, 100]),
                title="sub-score (0–100)", axis=_AXIS),
        tooltip=[alt.Tooltip("component:N"), alt.Tooltip("score:Q")],
    )
    bars = base.mark_bar(color=fx.MAGNITUDE_HUE, cornerRadiusEnd=4, size=16)
    labels = base.mark_text(align="left", dx=5, color=fx.NEUTRAL_INK).encode(text="score:Q")
    return (bars + labels).properties(height=len(rows) * 30 + 12).configure_view(stroke=None)




def rag_donut(counts: dict) -> alt.Chart:
    """RAG mix as a status-coloured donut (2px surface gap between arcs)."""
    df = pd.DataFrame([{"status": k, "n": v} for k, v in counts.items() if v])
    return (
        alt.Chart(df)
        .mark_arc(innerRadius=58, cornerRadius=2, stroke="#FFFFFF", strokeWidth=2)
        .encode(
            theta=alt.Theta("n:Q", stack=True),
            color=alt.Color("status:N",
                            scale=alt.Scale(domain=list(fx.RAG_COLOR),
                                            range=list(fx.RAG_COLOR.values())),
                            legend=alt.Legend(title=None, orient="bottom")),
            tooltip=[alt.Tooltip("status:N"), alt.Tooltip("n:Q", title="accounts")],
        )
        .properties(height=200)
    )




def csm_bar(per_csm: list[dict]) -> alt.Chart:
    """ACV-at-risk by CSM — magnitude bars, one hue, sorted descending."""
    rows = [r for r in per_csm if r.get("at_risk", 0) > 0] or per_csm
    df = pd.DataFrame(rows)
    base = alt.Chart(df).encode(
        y=alt.Y("csm:N", sort="-x", title=None, axis=_AXIS),
        x=alt.X("at_risk:Q", title="ACV at risk ($)", axis=_AXIS),
        tooltip=[alt.Tooltip("csm:N"), alt.Tooltip("at_risk:Q", title="ACV at risk", format="$,.0f")],
    )
    bars = base.mark_bar(color=fx.MAGNITUDE_HUE, cornerRadiusEnd=4, size=18)
    return bars.properties(height=len(rows) * 34 + 12).configure_view(stroke=None)




# ══════════════════════════════════════════════════════════════════════════════
# Streamlit shell
# ══════════════════════════════════════════════════════════════════════════════


_CSS = """
<style>
.fd-banner { padding:14px 18px; border-radius:8px; margin:4px 0 12px 0; border-left:6px solid; }
.fd-banner .t { font-size:1.45rem; font-weight:700; color:#1F2933; }
.fd-banner .s { color:#5B6570; font-size:0.9rem; margin-top:3px; }
.fd-red   { background:#FBEAEA; border-color:#D64545; }
.fd-amber { background:#FBF3DE; border-color:#E0A100; }
.fd-green { background:#E8F5EE; border-color:#2E9D63; }
.fd-flag  { display:inline-block; padding:4px 11px; margin:3px 6px 3px 0; border-radius:14px;
            background:#EEF3F3; border:1px solid #D6E0E0; font-size:0.85rem; color:#1F2933; }
.fd-flag b { color:#2C7A7B; }
.fd-chip  { display:inline-block; padding:2px 9px; margin:2px 4px 2px 0; border-radius:6px;
            background:#F0F3F4; color:#5B6570; font-size:0.8rem; }
.fd-action{ background:#E7F1F1; border-left:6px solid #2C7A7B; padding:12px 16px; border-radius:8px;
            font-weight:600; color:#1F2933; margin:6px 0; }
.fd-sec   { font-size:1.15rem; font-weight:700; color:#1F2933; margin:8px 0 2px 0; }
.fd-sec .n{ display:inline-block; background:#2C7A7B; color:#fff; border-radius:50%; width:24px;
            height:24px; text-align:center; line-height:24px; margin-right:8px; font-size:0.85rem; }
.fd-head  { display:flex; justify-content:space-between; align-items:center;
            border-bottom:2px solid #2C7A7B; padding-bottom:6px; margin-bottom:10px; }
.fd-head .b { font-size:1.4rem; font-weight:700; color:#1F2933; }
</style>
"""




# ── helpers ───────────────────────────────────────────────────────────────────


def _clean_mode(v: str) -> str:
    return v.split()[0]                          # "github (needs setup)" -> "github"




def _clean_quote(q: str) -> str:
    return q.strip().strip('"').strip("'").strip()




def _has_key(provider: str) -> bool:
    env = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "google": "GOOGLE_API_KEY"}
    return bool(os.getenv(env.get(provider, ""), ""))




@st.cache_data(show_spinner=False)
def _account_index():
    return fx.list_accounts()




@st.cache_data(show_spinner=False)
def _mock_comms(account_id: str) -> list[str]:
    """A safe, no-network preview of the raw comms (forces every source to mock)."""
    saved = {k: os.environ.get(k) for k in _MODE_KEYS}
    for k in _MODE_KEYS:
        os.environ[k] = "mock"
    try:
        return list(fx.get_account(account_id).recent_comms)
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)




def _run_live(account_id: str, src: dict) -> None:
    for k, v in src.items():
        os.environ[k] = _clean_mode(v)
    try:
        with st.spinner(f"Analyzing {account_id} — calling the model…"):
            state = fx.run_account(account_id)
        view = fx.to_view(state)
        view["sources"] = {k: _clean_mode(v) for k, v in src.items()}
        st.session_state.results[account_id] = view
        st.session_state.nav = "Account"
        st.toast(f"Analyzed {account_id}", icon="✅")
    except Exception as e:                                 # noqa: BLE001 — surface any failure in-UI
        st.error(f"Live run failed: {e}")




def _goto(account_id: str) -> None:
    st.session_state.account_id = account_id
    st.session_state.nav = "Account"




# ── sidebar ───────────────────────────────────────────────────────────────────


def sidebar() -> tuple[str, dict, bool]:
    st.sidebar.title("📊 Fieldora CS")
    mode = st.sidebar.radio("Mode", ["Replay (safe)", "Live (calls the model)"],
                            help="Replay renders saved runs instantly, no model calls. "
                                 "Live analyzes the selected account now.")
    live = mode.startswith("Live")


    st.sidebar.divider()
    st.sidebar.subheader("Data sources")
    if not live:
        st.sidebar.caption("Replay renders saved runs — these apply when you switch to Live.")
    src = {
        "CRM_MODE": st.sidebar.selectbox("CRM", ["mock", "csv"], disabled=not live),
        "PLATFORM_MODE": st.sidebar.selectbox("Platform", ["mock", "sqlite"], disabled=not live),
        "SUPPORT_MODE": st.sidebar.selectbox("Support", ["mock", "github (needs setup)"], disabled=not live),
        "EMAIL_MODE": st.sidebar.selectbox("Email", ["mock", "eml", "mcp (needs setup)"], disabled=not live),
        "SLACK_MODE": st.sidebar.selectbox("Slack", ["mock", "mcp (needs setup)"], disabled=not live),
    }


    st.sidebar.divider()
    accounts = _account_index()
    ids = [a["account_id"] for a in accounts]
    labels = {a["account_id"]: f"{a['account_id']} · {a['name']}" for a in accounts}
    if st.session_state.get("account_id") not in ids:          # keep the key valid before the widget
        st.session_state.account_id = ids[0]
    account_id = st.sidebar.selectbox("Account", ids, key="account_id", format_func=labels.get)


    st.sidebar.button("▶ Analyze this account", type="primary", disabled=not live,
                      use_container_width=True, on_click=_run_live, args=(account_id, src),
                      help=None if live else "Switch to Live mode to run the pipeline.")


    provider = os.getenv("LLM_PROVIDER", "anthropic")
    model = os.getenv(f"{provider.upper()}_MODEL") or "(provider default)"
    st.sidebar.caption(f"LLM: **{provider}** · {model}")
    if not _has_key(provider):
        st.sidebar.warning("No API key for this provider — Live runs will fail.")
    return account_id, src, live




# ── portfolio ───────────────────────────────────────────────────────────────


def render_portfolio(results: dict) -> None:
    st.subheader("Portfolio — the book, Monday morning")
    if not results:
        st.info("No analyzed accounts yet. In **Replay**, run `python -m fieldora --build-snapshots` "
                "first; in **Live**, analyze accounts from the sidebar.")
        return
    s = fx.portfolio_summary(results)


    pct = (s["at_risk_acv"] / s["total_acv"] * 100) if s["total_acv"] else 0
    cls = "fd-red" if s["exceeds_budget"] else "fd-green"
    warn = " &nbsp;⚠ exceeds churn budget" if s["exceeds_budget"] else ""
    st.markdown(
        f'<div class="fd-banner {cls}"><div class="t">{fx.money_short(s["at_risk_acv"])} '
        f'ACV at risk{warn}</div><div class="s">{pct:.0f}% of the '
        f'{fx.money_short(s["total_acv"])} book · GRR churn budget '
        f'{fx.money_short(s["churn_budget"])}</div></div>', unsafe_allow_html=True)


    c = st.columns(5)
    c[0].metric("🔴 RED", s["counts"]["RED"])
    c[1].metric("🟡 AMBER", s["counts"]["AMBER"])
    c[2].metric("🟢 GREEN", s["counts"]["GREEN"])
    c[3].metric("Book", fx.money_short(s["total_acv"]))
    c[4].metric("ACV at risk", fx.money_short(s["at_risk_acv"]))


    left, right = st.columns([1, 1.3])
    with left:
        st.caption("RAG mix")
        st.altair_chart(rag_donut(s["counts"]), use_container_width=True)
    with right:
        st.caption("ACV at risk by CSM")
        st.altair_chart(csm_bar(s["per_csm"]), use_container_width=True)


    if s["attention"]:
        st.subheader("Immediate attention")
        for v in s["attention"]:
            a, h = v["account"], v["health"]
            row = st.container(border=True)
            cc = row.columns([6, 1])
            cc[0].markdown(f"{fx.rag_icon('RED')} **{a['name']}** · {a['csm']} · "
                           f"{fx.money(a['acv_usd'])} · {a['days_to_renewal']}d to renewal "
                           f"· score {h['score']}")
            cc[1].button("Open →", key=f"open_{v['account_id']}",
                         on_click=_goto, args=(v["account_id"],))


    st.subheader("Book of business")
    st.dataframe(fx.book_rows(results), use_container_width=True, hide_index=True)




# ── account (vertical narrative) ──────────────────────────────────────────────


def render_account(account_id: str, results: dict, live: bool) -> None:
    view = results.get(account_id)
    if view is None:
        st.info(f"**{account_id}** hasn't been analyzed yet. "
                + ("Click **▶ Analyze this account** in the sidebar."
                   if live else "Switch to **Live** and analyze it, or run `--build-snapshots`."))
        with st.container(height=320):
            for d in _mock_comms(account_id):
                st.code(d, language=None)
        return


    _banner(view)
    _provenance(view)
    _why_score(view)
    st.divider()


    _section("①", "The raw signal — the mess")
    st.caption("~1 hour of manual reading a CSM does by hand every week")
    with st.container(height=320):
        for d in view["raw_comms"]:
            st.code(d, language=None)
    st.divider()


    _section("②", "The AI's structured, cited read")
    _grounding_badge(view["grounding"])
    if view["signals"]:
        _sentiment(view["signals"])
        _flags(view["signals"])
        _findings_grid(view["signals"])
    st.divider()


    _section("③", "The play — what the CSM does")
    if view["brief"]:
        _play(view["brief"])
    _telemetry(view)




def _banner(view: dict) -> None:
    a, h = view["account"], view["health"]
    cls = {"RED": "fd-red", "AMBER": "fd-amber", "GREEN": "fd-green"}.get(h["rag_status"], "fd-green")
    meta = " · ".join(x for x in (a["industry"], a["region"], a["stage"]) if x)
    sub = (f"{meta} &nbsp;·&nbsp; CSM {a['csm']} · {fx.money(a['acv_usd'])} · "
           f"renewal {a['days_to_renewal']}d · adoption {h['adoption_pct']}%")
    st.markdown(
        f'<div class="fd-banner {cls}"><div class="t">{fx.rag_icon(h["rag_status"])} '
        f'{a["name"]} &nbsp;—&nbsp; {h["rag_status"]} · {h["score"]}/100 '
        f'<span style="font-size:0.95rem;color:#5B6570;font-weight:400;">{fx.delta_str(h)}'
        f'</span></div><div class="s">{sub}</div></div>', unsafe_allow_html=True)




def _provenance(view: dict) -> None:
    srcs = view.get("sources")
    if not srcs:
        st.markdown('<span class="fd-chip">from saved snapshot</span>', unsafe_allow_html=True)
        return
    chips = " ".join(f'<span class="fd-chip">{c}</span>' for c in fx.provenance(srcs))
    st.markdown(f"Sourced from &nbsp;{chips}", unsafe_allow_html=True)




def _why_score(view: dict) -> None:
    h = view["health"]
    cols = st.columns([3, 1])
    with cols[0]:
        st.caption("Why this score — component sub-scores (0–100)")
        st.altair_chart(component_bars(fx.component_rows(h["components"])),
                        use_container_width=True)
    with cols[1]:
        st.caption("Overrides fired")
        if h.get("rules_fired"):
            for r in h["rules_fired"]:
                st.markdown(f'<span class="fd-chip">⚠ {r}</span>', unsafe_allow_html=True)
        else:
            st.caption("none")




def _section(n: str, title: str) -> None:
    st.markdown(f'<div class="fd-sec"><span class="n">{n}</span>{title}</div>', unsafe_allow_html=True)




def _grounding_badge(g: dict) -> None:
    if g["total"] == 0:
        st.caption("No citations produced.")
    elif not g["unsupported"]:
        st.success(f"✓ Grounding — all {g['grounded']} / {g['total']} citations verified "
                   f"verbatim against source")
    else:
        st.error(f"⚠ Grounding — {g['grounded']} / {g['total']} verified; "
                 f"{len(g['unsupported'])} not found in source")




def _sentiment(s: dict) -> None:
    cols = st.columns([1, 2])
    with cols[0]:
        st.metric("Sentiment", s["sentiment_label"], delta=f"{s['sentiment_score']:+.2f}",
                  delta_color="off")
        st.caption(f"overall confidence {s['overall_confidence']:.0%}")
    with cols[1]:
        for e in s["sentiment_evidence"]:
            st.caption(f"↳ {e['source']}: “{_clean_quote(e['quote'])}”")




def _flags(s: dict) -> None:
    fl = fx.flags(s)
    if not fl:
        return
    html = " ".join(f'<span class="fd-flag"><b>{f["kind"]}</b> &nbsp;“{_clean_quote(f["text"])}”</span>'
                    for f in fl)
    st.markdown(html, unsafe_allow_html=True)




_FINDING_GROUPS = [("Risks", "risks"), ("Stakeholder changes", "stakeholder_changes"),
                   ("Blockers", "blockers"), ("Open asks", "open_asks"), ("Commitments", "commitments")]




def _findings_grid(s: dict) -> None:
    groups = [(t, f) for t, f in _FINDING_GROUPS if s.get(f)]
    cols = st.columns(2)
    for i, (title, field) in enumerate(groups):
        with cols[i % 2]:
            st.markdown(f"**{title}**")
            for f in sorted(s[field], key=lambda x: x["confidence"], reverse=True):
                with st.container(border=True):
                    conf = f["confidence"]
                    flag = " · ⚠ low" if conf < 0.5 else ""
                    st.markdown(f"{f['summary']}  ·  **{conf:.0%}**{flag}")
                    st.progress(min(max(conf, 0.0), 1.0))
                    for e in f["evidence"]:
                        st.caption(f"↳ {e['source']}: “{_clean_quote(e['quote'])}”")
    if s.get("expansion_signals"):
        st.markdown("**Expansion signals**")
        st.markdown("\n".join(f'- “{_clean_quote(q)}”' for q in s["expansion_signals"]))




def _play(b: dict) -> None:
    st.markdown(f"### {b['headline']}")
    st.markdown(f"**Situation** — {b['situation']}")
    st.markdown("**Risk signals**")
    for r in b["risks"]:
        st.markdown(f"- {r}")
    st.markdown(f'<div class="fd-action">▶ Action this week — {b["action"]}</div>',
                unsafe_allow_html=True)
    st.markdown("**Draft** — review before sending (human in the loop)")
    st.code(b["draft"], language=None)




def _telemetry(view: dict) -> None:
    u = view.get("usage") or {}
    bits = []
    if u.get("total_tokens"):
        bits.append(f"{u['total_tokens']:,} tokens ({u.get('input_tokens', 0):,} in / "
                    f"{u.get('output_tokens', 0):,} out)")
    if view.get("latency_s") is not None:
        bits.append(f"{view['latency_s']}s model time")
    if view.get("attempts"):
        bits.append(f"{view['attempts']} extraction attempt(s)")
    if bits:
        st.caption(" · ".join(bits) + "  — extraction only")




# ── evals & how-it-works ──────────────────────────────────────────────────────


def render_evals(results: dict) -> None:
    st.subheader("Rubric evals — deterministic, no API key")
    st.caption("These pin the shared definition of health, including the renewal→RED override, and "
               "run with no model.")
    if st.button("Run rubric evals"):
        rows = [{"case": c["name"],
                 "result": "✓ PASS" if not fx.check_case(c) else "✗ FAIL",
                 "detail": "; ".join(fx.check_case(c))} for c in fx.RUBRIC_CASES]
        st.dataframe(rows, use_container_width=True, hide_index=True)


    if results:
        tot = sum(v["grounding"]["total"] for v in results.values())
        gr = sum(v["grounding"]["grounded"] for v in results.values())
        if tot:
            st.metric("Grounding rate across analyzed accounts", f"{gr}/{tot}",
                      f"{gr / tot:.0%}", delta_color="off")




def render_how() -> None:
    st.markdown(
        """
### How it works


```
data sources ─► extract_signals ─► verify (grounding gate) ─► score (rubric) ─► brief
 (mock|csv|      LLM: mess →         no LLM: every quote        no LLM:          LLM: the play,
  sqlite|eml|    cited structured    verbatim + source-scoped;  weighted rubric  grounded in the
  github|mcp)    read                re-ask once if any drop    (glass box)      verified findings
```


1. **Acquisition** is decoupled — flip any source (CSV / SQLite / `.eml` / GitHub / MCP) from the
   sidebar; the intelligence layer never changes.
2. **Extraction** (the heavy LLM step) turns messy multi-source comms into a *structured, cited* read.
3. **Grounding gate** (no LLM) verifies each quote is verbatim in the cited document; ungrounded
   citations are stripped and the agent re-asks once. Every claim has a receipt.
4. **Rubric** (no LLM) computes the score from hard signals — the LLM's only input is sentiment (15%),
   and it can't move the score without grounded evidence. Reproducible and explainable.
5. **Brief** drafts the branch-specific play, grounded in the verified findings — a human reviews it.
"""
    )




# ── entry ─────────────────────────────────────────────────────────────────────


def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    if "results" not in st.session_state:
        st.session_state.results = fx.load_snapshots()      # Replay preload (empty if none)
    st.session_state.setdefault("nav", "Portfolio")
    st.session_state.setdefault("account_id", "ACC-003")


    account_id, src, live = sidebar()


    badge = "🟢 LIVE" if live else "🔵 REPLAY"
    st.markdown(f'<div class="fd-head"><span class="b">Fieldora · CSM Account Intelligence</span>'
                f'<span class="fd-chip">{badge}</span></div>', unsafe_allow_html=True)


    view = st.radio("View", _VIEWS, key="nav", horizontal=True, label_visibility="collapsed")


    results = st.session_state.results
    if view == "Portfolio":
        render_portfolio(results)
    elif view == "Account":
        render_account(account_id, results, live)
    elif view == "Evals":
        render_evals(results)
    else:
        render_how()




main()