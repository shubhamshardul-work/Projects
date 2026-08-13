"""
tests.py — the whole offline test suite, consolidated into one file.


Run:  pytest tests.py     (fully offline — no API key, no network; the rubric + gate are pure Python)


This merges the original 17 test modules. Everything imports the single `fieldora` module; helper
constants/fixtures that collided across the original files are namespaced with a per-source prefix
(EXT_/GR_/UI_/_ext_/_gr_/_ui_…). Monkeypatch targets that used to point at submodule attributes
(e.g. crm_connector.CRM_CSV, agent._llm, support_connector.crosswalk.get) now point at the flat
`fieldora` module, since every symbol lives there.


The two opt-in LIVE evals (they actually call the model) are gated per-function with
`FIELDORA_RUN_LLM_EVALS=1`, so the default run stays offline. The DeepEval one also `importorskip`s
inside the test, so a missing optional extra skips just that test — not the whole file.
"""


import importlib.util
import json
import os


import pytest


import fieldora as fx
from fieldora import Account, AccountBrief, Evidence, ExtractedSignals, Finding, HealthScore




# ── shared autouse cleanup ────────────────────────────────────────────────────
# Both the GitHub issue fetch and the crosswalk table are memoized; clear them around every test so
# a stub or a tmp-path fixture from one test can never leak into another. (Replaces the original
# test_connectors_github autouse fixture + test_crosswalk teardown_module.)


@pytest.fixture(autouse=True)
def _clear_caches():
    fx.sources._fetch_issues.cache_clear()
    fx.sources._crosswalk_table.cache_clear()
    yield
    fx.sources._fetch_issues.cache_clear()
    fx.sources._crosswalk_table.cache_clear()




# ══════════════════════════════════════════════════════════════════════════════
# rubric — deterministic scoring engine (was tests/test_rubric.py)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("case", fx.RUBRIC_CASES, ids=[c["name"] for c in fx.RUBRIC_CASES])
def test_rubric_case(case):
    account = fx.get_account(case["account"])
    if case.get("override_account"):
        account = account.model_copy(update=case["override_account"])


    health = fx.compute_health(account, case["signals"])


    assert health.rag_status == case["expect_rag"]
    lo, hi = case["expect_score_range"]
    assert lo <= health.score <= hi
    if case.get("expect_rule_contains"):
        assert any(case["expect_rule_contains"] in r for r in health.rules_fired)




def test_weights_sum_to_one():
    assert round(sum(fx.WEIGHTS.values()), 6) == 1.0




def test_count_delayed_milestones_is_deterministic():
    # Milestone delays are parsed from the status string (system of record), not guessed by the LLM.
    assert fx.count_delayed_milestones("Advanced workflows: DELAYED | Reporting module: NOT STARTED") == 2
    assert fx.count_delayed_milestones("All milestones: COMPLETE") == 0
    assert fx.count_delayed_milestones("Compliance reporting: DELAYED | Core scheduling: COMPLETE") == 1
    assert fx.count_delayed_milestones(
        "Go-live: COMPLETE | First workflow adoption: DELAYED (past 90-day TTV) | Training: NOT STARTED"
    ) == 2
    assert fx.count_delayed_milestones("") == 0




# ══════════════════════════════════════════════════════════════════════════════
# observability — token/latency capture (was tests/test_observability.py)
# ══════════════════════════════════════════════════════════════════════════════


class _FakeRawObs:
    def __init__(self, usage_metadata):
        self.usage_metadata = usage_metadata




def test_usage_from_raw_reads_tokens():
    raw = _FakeRawObs({"input_tokens": 100, "output_tokens": 40, "total_tokens": 140})
    assert fx.usage_from_raw(raw) == {
        "input_tokens": 100, "output_tokens": 40, "total_tokens": 140,
    }




def test_usage_from_raw_empty_when_unavailable():
    assert fx.usage_from_raw(None) == {}
    assert fx.usage_from_raw(_FakeRawObs(None)) == {}




def test_summarize_aggregates_across_results():
    results = [
        {"usage": {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140}, "latency_s": 1.5},
        {"usage": {"input_tokens": 50, "output_tokens": 10, "total_tokens": 60}, "latency_s": 0.5},
        {"usage": None, "latency_s": None},  # stubbed/missing usage must not crash
    ]
    s = fx.summarize(results)
    assert s["accounts"] == 3
    assert s["total_tokens"] == 200
    assert abs(s["latency_s"] - 2.0) < 1e-6




# ══════════════════════════════════════════════════════════════════════════════
# prompts — the brief's analyst-read formatter (was tests/test_prompts.py)
# ══════════════════════════════════════════════════════════════════════════════


def _prompts_rich_signals() -> ExtractedSignals:
    return ExtractedSignals(
        sentiment_score=-0.6, sentiment_label="NEGATIVE", key_themes=["outages"],
        churn_signals=["still waiting"], expansion_signals=[],
        risks=[Finding(summary="Repeated outages eroding trust", confidence=0.9,
                       evidence=[Evidence(source="SUPPORT TKT-847", quote="two related outages")])],
        competitor_mentions=["looking at what else is out there"],
        stakeholder_changes=[Finding(summary="New VP reviewing vendors", confidence=0.8,
                       evidence=[Evidence(source="CRM_NOTE", quote="reviewing all vendor contracts")])],
    )




def test_analyst_read_includes_findings_and_citations():
    out = fx.build_brief_analyst_read(_prompts_rich_signals())
    assert "Repeated outages eroding trust" in out
    assert "two related outages" in out and "SUPPORT TKT-847" in out
    assert "Competitor mentions" in out and "looking at what else is out there" in out
    assert "Stakeholder changes" in out and "New VP reviewing vendors" in out




def test_analyst_read_sorts_findings_by_confidence():
    s = ExtractedSignals(
        sentiment_score=-0.5, sentiment_label="NEGATIVE", key_themes=[],
        churn_signals=[], expansion_signals=[],
        risks=[
            Finding(summary="low conf risk", confidence=0.3,
                    evidence=[Evidence(source="EMAIL", quote="two related outages")]),
            Finding(summary="high conf risk", confidence=0.95,
                    evidence=[Evidence(source="EMAIL", quote="two related outages")]),
        ],
    )
    out = fx.build_brief_analyst_read(s)
    assert out.index("high conf risk") < out.index("low conf risk")




def test_analyst_read_empty_when_nothing_extracted():
    s = ExtractedSignals(sentiment_score=0.0, sentiment_label="NEUTRAL",
                         key_themes=[], churn_signals=[], expansion_signals=[])
    assert fx.build_brief_analyst_read(s) == ""




# ══════════════════════════════════════════════════════════════════════════════
# extraction service + grounding-gate wiring (was tests/test_extraction.py)
# ══════════════════════════════════════════════════════════════════════════════


RAW_EXT = "[EMAIL] Frankly, this is unacceptable.\n\n[SUPPORT TKT-1] latency is high during peak."




class _ExtStubStructured:
    """Mimics llm.with_structured_output(..., include_raw=True): .invoke -> {parsed, raw, error}."""
    def __init__(self, parsed, raw=None, parsing_error=None):
        self._parsed = parsed
        self._raw = raw
        self._error = parsing_error


    def invoke(self, _messages):
        return {"raw": self._raw, "parsed": self._parsed, "parsing_error": self._error}




def _ext_account() -> Account:
    return Account(
        account_id="ACC-X", name="Test", csm="X", acv_usd=100000, account_age_months=6,
        modules_licensed=4, modules_active=2, logins_last_30d=5, days_since_csm_contact=10,
        open_tickets=1, days_to_renewal=100, milestone_status="All milestones: COMPLETE",
        recent_comms=[RAW_EXT],
    )




def _ext_signals_fabricated() -> ExtractedSignals:
    return ExtractedSignals(
        sentiment_score=-0.5, sentiment_label="NEGATIVE", key_themes=["x"],
        churn_signals=["this is unacceptable"],                       # grounded
        expansion_signals=[],
        risks=[
            Finding(summary="latency", confidence=0.9,
                    evidence=[Evidence(source="SUPPORT TKT-1", quote="latency is high")]),   # grounded
            Finding(summary="made up", confidence=0.4,
                    evidence=[Evidence(source="X", quote="totally fabricated quote")]),       # NOT grounded
        ],
    )




def _ext_base_state(**kw):
    st = {"account_id": "ACC-X", "account": _ext_account(), "signals": None, "health": None,
          "brief": None, "raw_comms": RAW_EXT, "attempts": 1, "dropped": [],
          "grounding_feedback": None, "parse_error": None, "usage": None, "latency_s": None}
    st.update(kw)
    return st




def test_extraction_service_unwraps_include_raw():
    parsed = _ext_signals_fabricated()
    signals, raw, err = fx.extract(_ExtStubStructured(parsed), _ext_account(), RAW_EXT)
    assert signals is parsed and raw is None and err is None




def test_filter_grounded_drops_fabricated_finding():
    s, dropped = fx.filter_grounded(_ext_signals_fabricated(), RAW_EXT)
    summaries = [f.summary for f in s.risks]
    assert "latency" in summaries and "made up" not in summaries
    assert any("made up" in d for d in dropped)
    assert s.churn_signals == ["this is unacceptable"]  # grounded quote survives




def test_verify_reasks_when_attempts_remain_then_proceeds():
    out = fx.verify_signals(_ext_base_state(signals=_ext_signals_fabricated(), attempts=1))
    assert out["dropped"] and fx.route_after_verify(out) == "extract_signals"


    out2 = fx.verify_signals(_ext_base_state(signals=_ext_signals_fabricated(),
                                             attempts=fx.MAX_EXTRACT_ATTEMPTS))
    assert fx.route_after_verify(out2) == "score_account"     # no attempts left → proceed grounded-only




def test_verify_handles_parse_failure_gracefully():
    out = fx.verify_signals(_ext_base_state(signals=None, attempts=fx.MAX_EXTRACT_ATTEMPTS))
    assert out["signals"] is not None and out["signals"].sentiment_label == "NEUTRAL"
    assert fx.route_after_verify(out) == "score_account"




def test_parse_error_flows_into_reask_feedback():
    out = fx.verify_signals(_ext_base_state(signals=None, attempts=1,
                                            parse_error="sentiment_score: Input should be <= 1.0"))
    assert fx.route_after_verify(out) == "extract_signals"
    assert "sentiment_score" in out["grounding_feedback"]




class _ExtFakeRaw:
    """Stand-in AIMessage carrying token usage (what with_structured_output(include_raw) returns)."""
    usage_metadata = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}




class _ExtStubLLM:
    def with_structured_output(self, *a, **k):
        return object()   # unused — fx.extract is monkeypatched below




def test_extract_signals_accumulates_usage_across_attempts(monkeypatch):
    # A re-ask is a second billed call; usage/latency must sum, not overwrite.
    signals = _ext_signals_fabricated()
    monkeypatch.setattr(fx.agent, "_llm", lambda: _ExtStubLLM())
    monkeypatch.setattr(fx.agent, "extract",
                        lambda structured, account, comms, feedback=None: (signals, _ExtFakeRaw(), None))


    out1 = fx.extract_signals(_ext_base_state(attempts=0, usage=None, latency_s=None))
    assert out1["usage"]["total_tokens"] == 120 and out1["attempts"] == 1


    out2 = fx.extract_signals(out1)   # simulate the grounded re-ask
    assert out2["usage"]["total_tokens"] == 240 and out2["attempts"] == 2




def test_coverage_counts_present_categories():
    s = ExtractedSignals(
        sentiment_score=-0.5, sentiment_label="NEGATIVE", key_themes=[],
        churn_signals=["x"], expansion_signals=[],
        risks=[Finding(summary="r", evidence=[Evidence(source="S", quote="latency is high")])],
    )
    assert fx.coverage(s, ["risks", "churn_signals", "competitor_mentions"]) == (2, 3)




def test_render_comms_caps_to_most_recent():
    a = _ext_account()
    body = "x" * 400
    a.recent_comms = [
        f"[EMAIL | 2026-01-01 | a@x]\noldest {body}",           # oldest by date
        f"[EMAIL | 2026-08-05 | b@x]\nnewest {body}",           # newest by date
        f"[SUPPORT | TKT-9 | open 3d]\nundated ticket {body}",  # no date → treated as current
    ]
    out = fx.render_comms(a, max_chars=1000)   # room for ~2 of the ~440-char docs
    assert "newest" in out            # most-recent dated kept
    assert "undated ticket" in out    # undated live doc retained (not dropped first)
    assert "oldest" not in out        # oldest dated dropped
    assert len(out) <= 1000




def test_render_comms_untouched_when_under_budget():
    a = _ext_account()
    a.recent_comms = ["[EMAIL | 2026-01-01 | a]\nfirst", "[EMAIL | 2026-08-05 | b]\nsecond"]
    out = fx.render_comms(a)
    assert out == "[EMAIL | 2026-01-01 | a]\nfirst\n\n[EMAIL | 2026-08-05 | b]\nsecond"




# ══════════════════════════════════════════════════════════════════════════════
# grounding — anti-hallucination check (was tests/test_grounding.py)
# ══════════════════════════════════════════════════════════════════════════════


RAW_GR = """
### [EMAIL | 2026-08-03 | ops.lead@novapower.example]
Honestly this is unacceptable — second outage this month.


### [SLACK | #cs-novapower | 2026-08-05]
renewal in 45d, adoption ~40%, compliance report still delayed
""".strip()




def _gr_signals(**kw) -> ExtractedSignals:
    base = dict(
        sentiment_score=-0.6, sentiment_label="NEGATIVE",
        key_themes=["outages"], churn_signals=[], expansion_signals=[],
    )
    base.update(kw)
    return ExtractedSignals(**base)




def test_grounded_quotes_pass():
    s = _gr_signals(
        sentiment_evidence=[Evidence(source="EMAIL", quote="this is unacceptable")],
        churn_signals=["compliance report still delayed"],
    )
    assert fx.verify_grounding(s, RAW_GR) == []




def test_hallucinated_quote_is_flagged():
    s = _gr_signals(sentiment_evidence=[Evidence(source="EMAIL", quote="we love this product")])
    bad = fx.verify_grounding(s, RAW_GR)
    assert len(bad) == 1
    assert "we love this product" in bad[0]




def test_case_and_whitespace_insensitive():
    s = _gr_signals(churn_signals=["Honestly   this is   UNACCEPTABLE"])
    assert fx.verify_grounding(s, RAW_GR) == []




def test_edge_punctuation_and_dash_variants_still_match():
    s = _gr_signals(churn_signals=[
        '"this is unacceptable."',          # wrapped in quotes + trailing period
        "unacceptable - second outage",     # hyphen vs the source's em-dash
    ])
    assert fx.verify_grounding(s, RAW_GR) == []




def test_summary_counts_grounded_vs_total():
    s = _gr_signals(
        sentiment_evidence=[Evidence(source="EMAIL", quote="this is unacceptable")],       # grounded
        risks=[Finding(summary="churn risk",
                       evidence=[Evidence(source="X", quote="totally made up quote")])],   # not grounded
    )
    total, grounded, bad = fx.grounding_summary(s, RAW_GR)
    assert total == 2
    assert grounded == 1
    assert len(bad) == 1




# source-scoped grounding + auto-repair of mis-attribution
RAW_DOCS_GR = "\n\n".join([
    "[EMAIL | 2026-08-05 | dana@x → sarah@y]\nFrankly, this is unacceptable.",
    "[SUPPORT | TKT-847 | open 12d]\nTwo related outages logged this month.",
])




def _gr_risk(source: str, quote: str, summary: str = "outages") -> ExtractedSignals:
    return _gr_signals(risks=[Finding(summary=summary, confidence=0.9,
                                      evidence=[Evidence(source=source, quote=quote)])])




def test_correct_attribution_is_kept_unchanged():
    s = _gr_risk("SUPPORT TKT-847", "Two related outages logged this month.")
    filtered, dropped = fx.filter_grounded(s, RAW_DOCS_GR)
    assert dropped == [] and filtered.risks
    assert filtered.risks[0].evidence[0].source == "SUPPORT TKT-847"   # untouched




def test_misattributed_quote_is_kept_and_source_repaired():
    s = _gr_risk("EMAIL 2026-08-05", "Two related outages logged this month.")
    filtered, dropped = fx.filter_grounded(s, RAW_DOCS_GR)
    assert dropped == [] and filtered.risks                            # not dropped
    assert filtered.risks[0].evidence[0].source == "SUPPORT TKT-847"   # auto-corrected




def test_fabricated_quote_is_still_dropped():
    s = _gr_risk("EMAIL 2026-08-05", "we love this product", summary="fake")
    filtered, dropped = fx.filter_grounded(s, RAW_DOCS_GR)
    assert filtered.risks == [] and any("fake" in d for d in dropped)




def test_unresolvable_source_falls_back_to_corpus_no_false_drop():
    s = _gr_risk("some-unknown-label", "this is unacceptable")
    filtered, dropped = fx.filter_grounded(s, RAW_DOCS_GR)
    assert dropped == [] and filtered.risks




def test_sentiment_label_reconciled_to_score():
    assert ExtractedSignals(sentiment_score=0.4, sentiment_label="NEGATIVE",
                            key_themes=[], churn_signals=[], expansion_signals=[]).sentiment_label == "POSITIVE"
    assert ExtractedSignals(sentiment_score=-0.4, sentiment_label="POSITIVE",
                            key_themes=[], churn_signals=[], expansion_signals=[]).sentiment_label == "NEGATIVE"
    assert ExtractedSignals(sentiment_score=0.05, sentiment_label="POSITIVE",
                            key_themes=[], churn_signals=[], expansion_signals=[]).sentiment_label == "NEUTRAL"




def test_uncorroborated_sentiment_is_neutralized():
    s = _gr_signals(sentiment_score=-0.8, churn_signals=[])   # no evidence, no churn, no risks
    out, changed = fx.enforce_sentiment_grounding(s)
    assert changed and out.sentiment_label == "NEUTRAL" and out.sentiment_score == 0.0




def test_corroborated_sentiment_survives():
    s = _gr_signals(sentiment_score=-0.8, churn_signals=["still waiting"])   # churn corroborates
    out, changed = fx.enforce_sentiment_grounding(s)
    assert not changed and out.sentiment_label == "NEGATIVE"




# ══════════════════════════════════════════════════════════════════════════════
# CRM CSV backend (was tests/test_connectors_csv.py)
# ══════════════════════════════════════════════════════════════════════════════


def test_crm_csv_reads_and_casts(tmp_path):
    path = tmp_path / "crm.csv"
    fx.build_crm_csv(path)
    row = fx.sources._get_csv("ACC-001", path=path)
    assert row["name"] == "Meridian Telecom"
    assert row["csm"] == "Sarah Chen"
    assert row["acv_usd"] == 1200000 and isinstance(row["acv_usd"], int)   # numeric cast from str
    assert isinstance(row["days_to_renewal"], int)




def test_crm_csv_lists_portfolio(tmp_path):
    path = tmp_path / "crm.csv"
    fx.build_crm_csv(path)
    accts = fx.sources._list_csv(path=path)
    assert any(a["account_id"] == "ACC-001" for a in accts)
    assert all({"account_id", "name", "csm"} <= a.keys() for a in accts)




def test_crm_csv_missing_account_raises(tmp_path):
    path = tmp_path / "crm.csv"
    fx.build_crm_csv(path)
    with pytest.raises(ValueError):
        fx.sources._get_csv("ACC-999", path=path)




def test_crm_csv_autobuilds_when_missing(tmp_path):
    path = tmp_path / "crm.csv"          # does not exist yet
    row = fx.sources._get_csv("ACC-001", path=path)   # _rows() auto-builds it
    assert path.exists() and row["name"] == "Meridian Telecom"




# ══════════════════════════════════════════════════════════════════════════════
# platform SQLite backend (was tests/test_connectors_sqlite.py)
# ══════════════════════════════════════════════════════════════════════════════


def test_sqlite_reads_usage_row(tmp_path):
    db = tmp_path / "fieldora.db"
    fx.build_usage_db(db)
    usage = fx.sources._get_sqlite("ACC-001", path=db)
    assert usage["modules_licensed"] == 8
    assert usage["modules_active"] == 3
    assert isinstance(usage["logins_last_30d"], int)
    assert usage["milestone_status"].startswith("Advanced workflows")




def test_sqlite_missing_account_raises(tmp_path):
    db = tmp_path / "fieldora.db"
    fx.build_usage_db(db)
    with pytest.raises(ValueError):
        fx.sources._get_sqlite("ACC-999", path=db)




def test_sqlite_autobuilds_when_missing(tmp_path):
    db = tmp_path / "fieldora.db"        # does not exist yet
    usage = fx.sources._get_sqlite("ACC-002", path=db)   # ensure builds it
    assert db.exists() and usage["modules_active"] == 5




# ══════════════════════════════════════════════════════════════════════════════
# email .eml backend (was tests/test_connectors_eml.py)
# ══════════════════════════════════════════════════════════════════════════════


def test_eml_roundtrip_preserves_header_date_and_body(tmp_path):
    root = tmp_path / "email"
    fx.build_email_dir(root)
    docs = fx.sources._get_eml("ACC-003", root=root)   # ACC-003 has rich email in the corpus
    assert docs, "expected .eml documents for ACC-003"
    joined = "\n\n".join(docs).lower()
    assert docs[0].startswith("[EMAIL |") and "subject:" in docs[0].lower()
    assert "2026-08-05" in joined          # the header date survived the RFC-822 round-trip
    assert "unacceptable" in joined        # the body survived




def test_eml_unknown_account_is_empty(tmp_path):
    root = tmp_path / "email"
    fx.build_email_dir(root)
    assert fx.sources._get_eml("ACC-999", root=root) == []




# ══════════════════════════════════════════════════════════════════════════════
# identity crosswalk (was tests/test_crosswalk.py)
# ══════════════════════════════════════════════════════════════════════════════


def test_crosswalk_reads_mapped_row(tmp_path, monkeypatch):
    path = tmp_path / "crosswalk.csv"
    fx.build_crosswalk_csv(path)
    monkeypatch.setattr(fx.sources, "CROSSWALK_CSV", path)
    fx.sources._crosswalk_table.cache_clear()


    row = fx.crosswalk_get("ACC-001")
    assert row["slack_channel"].startswith("#cs-")
    assert " OR " in row["gmail_query"]      # from:… OR to:…
    assert row["github_repo"] == ""          # blank by default (user maps a public repo)




def test_crosswalk_derives_fallback_for_unmapped(tmp_path, monkeypatch):
    path = tmp_path / "crosswalk.csv"
    path.write_text("account_id,slack_channel,gmail_query,github_repo\n", encoding="utf-8")  # header only
    monkeypatch.setattr(fx.sources, "CROSSWALK_CSV", path)
    fx.sources._crosswalk_table.cache_clear()


    row = fx.crosswalk_get("ACC-001")        # not in the table → derived
    assert row["slack_channel"] == "#cs-meridian-telecom"




# ══════════════════════════════════════════════════════════════════════════════
# aggregation-layer resilience (was tests/test_data_source_partial_failure.py)
# ══════════════════════════════════════════════════════════════════════════════


def test_comms_source_outage_is_tolerated(monkeypatch):
    def _down(account_id):
        raise RuntimeError("slack API down")


    monkeypatch.setattr(fx.sources, "slack_get_messages", _down)
    acct = fx.get_account("ACC-001")                      # everything else still mock
    assert acct.account_id == "ACC-001"
    assert acct.recent_comms                              # assembled from the surviving sources
    assert acct.modules_licensed == 8                     # structured fields intact




def test_scoring_input_source_failure_propagates(monkeypatch):
    def _down(account_id):
        raise RuntimeError("usage warehouse down")


    monkeypatch.setattr(fx.sources, "get_usage", _down)
    with pytest.raises(RuntimeError):                     # can't score without usage → hard fail
        fx.get_account("ACC-001")




# ══════════════════════════════════════════════════════════════════════════════
# end-to-end acquisition from REAL sources, no LLM (was tests/test_mode_dispatch.py)
# ══════════════════════════════════════════════════════════════════════════════


def test_get_account_from_csv_and_sqlite(tmp_path, monkeypatch):
    crm_csv = tmp_path / "crm.csv"
    db = tmp_path / "fieldora.db"
    fx.build_crm_csv(crm_csv)
    fx.build_usage_db(db)


    monkeypatch.setattr(fx.sources, "CRM_CSV", crm_csv)
    monkeypatch.setattr(fx.sources, "USAGE_DB", db)
    monkeypatch.setenv("CRM_MODE", "csv")
    monkeypatch.setenv("PLATFORM_MODE", "sqlite")


    acct = fx.get_account("ACC-001")                     # comms stay mock; no LLM anywhere
    assert acct.name == "Meridian Telecom"
    assert acct.csm == "Sarah Chen"
    assert acct.acv_usd == 1200000                        # from the CSV
    assert acct.modules_licensed == 8                     # from the SQLite read
    assert acct.days_to_renewal == 68




def test_default_mode_is_mock(monkeypatch):
    monkeypatch.delenv("CRM_MODE", raising=False)
    monkeypatch.delenv("PLATFORM_MODE", raising=False)
    acct = fx.get_account("ACC-002")
    assert acct.name == "Apex Utilities" and acct.modules_active == 5




# ══════════════════════════════════════════════════════════════════════════════
# support GitHub-Issues backend, network stubbed (was tests/test_connectors_github.py)
# ══════════════════════════════════════════════════════════════════════════════


_FAKE_ISSUES_GH = [
    {"number": 12, "state": "open", "title": "Scheduling module down",
     "body": "Crews idle during the 6am dispatch window."},
    {"number": 13, "state": "open", "title": "This is a PR, not a ticket",
     "body": "x", "pull_request": {"url": "https://api.github.com/…/pulls/13"}},
]




def test_github_maps_issues_and_filters_prs(monkeypatch):
    monkeypatch.setenv("SUPPORT_MODE", "github")
    monkeypatch.setenv("GITHUB_REPO", "octo/repo")
    monkeypatch.setattr(fx.sources, "crosswalk_get",
                        lambda aid: {"github_repo": "", "slack_channel": "", "gmail_query": ""})
    monkeypatch.setattr(fx.sources, "get_json", lambda *a, **k: _FAKE_ISSUES_GH)


    docs = fx.support_get_messages("ACC-001")
    assert len(docs) == 1                                   # PR (#13) filtered out
    assert docs[0].startswith("[SUPPORT | #12 | open]")
    assert "Scheduling module down" in docs[0]
    assert fx.get_open_ticket_count("ACC-001") == 1




def test_github_unmapped_repo_returns_empty_without_fetching(monkeypatch):
    monkeypatch.setenv("SUPPORT_MODE", "github")
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    monkeypatch.setattr(fx.sources, "crosswalk_get",
                        lambda aid: {"github_repo": "", "slack_channel": "", "gmail_query": ""})


    def _boom(*a, **k):
        raise AssertionError("must not fetch when no repo is mapped")


    monkeypatch.setattr(fx.sources, "get_json", _boom)
    assert fx.support_get_messages("ACC-001") == []




# ══════════════════════════════════════════════════════════════════════════════
# MCP backends — the guards only (was tests/test_connectors_mcp.py)
# ══════════════════════════════════════════════════════════════════════════════


_HAS_ADAPTER = importlib.util.find_spec("langchain_mcp_adapters") is not None




def test_connectors_import_without_the_extra():
    assert callable(fx.sources._get_slack_mcp)
    assert callable(fx.sources._get_gmail_mcp)




def test_server_config_requires_env(monkeypatch):
    monkeypatch.delenv("SLACK_MCP_COMMAND", raising=False)
    monkeypatch.delenv("SLACK_MCP_URL", raising=False)
    with pytest.raises(RuntimeError, match="not configured"):
        fx.server_config("SLACK")




def test_server_config_stdio_from_command(monkeypatch):
    monkeypatch.delenv("SLACK_MCP_URL", raising=False)
    monkeypatch.setenv("SLACK_MCP_COMMAND", "npx -y @modelcontextprotocol/server-slack")
    cfg = fx.server_config("SLACK")
    assert cfg["transport"] == "stdio" and cfg["command"] == "npx"
    assert cfg["args"][:2] == ["-y", "@modelcontextprotocol/server-slack"]




@pytest.mark.skipif(_HAS_ADAPTER, reason="adapter installed → the not-installed guard can't be exercised")
def test_with_tools_without_adapter_raises_clear_error(monkeypatch):
    monkeypatch.setenv("SLACK_MCP_COMMAND", "echo test")


    async def _run(tools):
        return []


    with pytest.raises(RuntimeError, match="MCP support not installed"):
        fx.with_tools("SLACK", _run)




# ══════════════════════════════════════════════════════════════════════════════
# UI presenter — the pure core of the dashboard (was tests/test_ui_presenter.py)
# ══════════════════════════════════════════════════════════════════════════════


RAW_UI = "[EMAIL] Frankly, this is unacceptable.\n\n[SUPPORT TKT-1] latency is high during peak."




def _ui_account() -> Account:
    return Account(
        account_id="ACC-X", name="Test Co", csm="Sarah Chen", industry="utilities", region="US",
        stage="live", acv_usd=600000, account_age_months=7, modules_licensed=5, modules_active=2,
        logins_last_30d=4, days_since_csm_contact=20, open_tickets=3, days_to_renewal=45,
        milestone_status="Compliance reporting: DELAYED", recent_comms=RAW_UI.split("\n\n"),
    )




def _ui_signals() -> ExtractedSignals:
    return ExtractedSignals(
        sentiment_score=-0.8, sentiment_label="NEGATIVE", key_themes=["outages"],
        churn_signals=["this is unacceptable"],                 # grounded
        expansion_signals=[],
        sentiment_evidence=[Evidence(source="EMAIL", quote="this is unacceptable")],   # grounded
        risks=[Finding(summary="churn risk", confidence=0.9,
                       evidence=[Evidence(source="X", quote="totally made up quote")])],  # NOT grounded
    )




def _ui_state() -> dict:
    account, signals = _ui_account(), _ui_signals()
    health = HealthScore(score=38, rag_status="RED", adoption_pct=40.0,
                         components={"adoption": 50, "engagement": 40, "recency": 27,
                                     "friction": 40, "sentiment": 10, "milestone": 60},
                         rules_fired=["renewal <90d → RED"], previous_score=42, delta=-4)
    brief = AccountBrief(brief_type="RETENTION", headline="At risk", situation="Outages.",
                         risks=["r1", "r2"], action="Call today", draft="Hi — ...")
    return {"account_id": "ACC-X", "account": account, "signals": signals, "health": health,
            "brief": brief, "usage": {"total_tokens": 3200, "input_tokens": 2200, "output_tokens": 1000},
            "latency_s": 6.1, "attempts": 1}




def test_to_view_shape_and_grounding():
    v = fx.to_view(_ui_state())
    assert v["account"]["name"] == "Test Co" and v["account"]["acv_usd"] == 600000
    assert v["health"]["rag_status"] == "RED" and v["health"]["score"] == 38
    assert v["signals"]["sentiment_label"] == "NEGATIVE"
    assert v["brief"]["brief_type"] == "RETENTION"
    # grounding: sentiment quote + churn quote grounded; the fabricated risk quote is not
    assert v["grounding"]["total"] == 3
    assert v["grounding"]["grounded"] == 2
    assert len(v["grounding"]["unsupported"]) == 1
    assert v["raw_comms"] == RAW_UI.split("\n\n")




def test_to_view_serializable_and_snapshot_roundtrip(tmp_path):
    v = fx.to_view(_ui_state())
    json.dumps(v)                                   # must be JSON-serializable
    snap = tmp_path / "snapshots.json"
    fx.save_snapshot(v, path=snap)
    loaded = fx.load_snapshots(path=snap)
    assert loaded["ACC-X"]["health"]["score"] == 38
    assert loaded["ACC-X"]["grounding"]["grounded"] == 2




def test_component_rows_ordered():
    rows = fx.component_rows({"sentiment": 10, "adoption": 50, "milestone": 60,
                              "engagement": 40, "recency": 27, "friction": 40})
    assert [r["component"] for r in rows] == \
        ["adoption", "engagement", "recency", "friction", "sentiment", "milestone"]




def _ui_view(aid, csm, rag, acv, score, renewal):
    return {"account_id": aid,
            "account": {"name": aid, "csm": csm, "acv_usd": acv, "days_to_renewal": renewal},
            "health": {"rag_status": rag, "score": score},
            "grounding": {"total": 0, "grounded": 0}}




def test_portfolio_summary_math():
    views = {
        "A": _ui_view("A", "Sarah", "RED", 100000, 30, 20),
        "B": _ui_view("B", "Sarah", "RED", 200000, 25, 10),
        "C": _ui_view("C", "Marcus", "GREEN", 300000, 90, 200),
    }
    s = fx.portfolio_summary(views)
    assert s["counts"] == {"RED": 2, "AMBER": 0, "GREEN": 1}
    assert s["total_acv"] == 600000 and s["at_risk_acv"] == 300000
    assert round(s["churn_budget"]) == 60000 and s["exceeds_budget"] is True
    # per-CSM: Sarah holds all at-risk ACV, sorted first
    assert s["per_csm"][0]["csm"] == "Sarah" and s["per_csm"][0]["at_risk"] == 300000
    # attention sorted by soonest renewal
    assert [v["account_id"] for v in s["attention"]] == ["B", "A"]




def test_formatters():
    assert fx.money(600000) == "$600,000"
    assert fx.rag_icon("RED") == "🔴"
    assert fx.delta_str({"delta": -4}).startswith("▼")
    assert fx.delta_str({"delta": None}) == "baseline set"




def test_money_short():
    assert fx.money_short(1_200_000) == "$1.2M"
    assert fx.money_short(600_000) == "$600K"
    assert fx.money_short(900) == "$900"
    assert fx.money_short(None) == "—"




def test_provenance_labels():
    chips = fx.provenance({"CRM_MODE": "csv", "PLATFORM_MODE": "sqlite",
                           "EMAIL_MODE": "eml", "SUPPORT_MODE": "github (needs setup)"})
    assert "CRM: csv" in chips and "Platform: sqlite" in chips
    assert "Support: github" in chips           # suffix stripped




def test_flags_selects_competitor_and_churn():
    fl = fx.flags({"competitor_mentions": ["what else is out there"],
                   "churn_signals": ["not in a good spot"],
                   "stakeholder_changes": [{"summary": "new VP", "evidence": [], "confidence": 0.9}]})
    kinds = {f["kind"] for f in fl}
    assert kinds == {"Competitor", "Churn"}       # stakeholder stays a card, not a flag
    assert any(f["text"] == "what else is out there" for f in fl)




# ══════════════════════════════════════════════════════════════════════════════
# OPT-IN LIVE EVALS — call the model; gated by FIELDORA_RUN_LLM_EVALS=1
# (was tests/test_extraction_quality.py + tests/test_faithfulness_deepeval.py)
# ══════════════════════════════════════════════════════════════════════════════


_GOLD = fx.eval_gold() if fx.SEED_JSON.exists() else {}


_LIVE_REASON = "live extraction eval — set FIELDORA_RUN_LLM_EVALS=1 and a provider key to run"




@pytest.mark.skipif(not os.getenv("FIELDORA_RUN_LLM_EVALS"), reason=_LIVE_REASON)
@pytest.mark.parametrize("account_id", list(_GOLD.keys()))
def test_extraction_quality(account_id):
    gold = _GOLD[account_id]
    acct = fx.get_account(account_id)
    state = {"account_id": account_id, "account": acct, "signals": None, "health": None,
             "brief": None, "raw_comms": None, "attempts": 0, "dropped": [],
             "grounding_feedback": None, "usage": None, "latency_s": None}
    out = fx.extract_signals(state)
    signals, raw = out["signals"], out["raw_comms"]


    assert signals is not None, "extraction did not parse"
    assert signals.sentiment_label == gold["expect_sentiment"]


    found, total = fx.coverage(signals, gold["expect_present"])
    assert found >= total - 1, f"coverage {found}/{total} below threshold"


    # faithfulness of the RAW model output (pre-gate): every citation must be verbatim
    assert not fx.verify_grounding(signals, raw), "raw extraction had ungrounded citations"




@pytest.mark.skipif(not os.getenv("FIELDORA_RUN_LLM_EVALS"),
                    reason="LLM-as-judge eval — set FIELDORA_RUN_LLM_EVALS=1 and a provider key to run")
def test_citation_entailment():
    pytest.importorskip("deepeval", reason="deepeval is an optional dev extra; install to run this")
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams


    acct = fx.get_account("ACC-003")
    state = {"account_id": "ACC-003", "account": acct, "signals": None, "health": None,
             "brief": None, "raw_comms": None, "attempts": 0, "dropped": [],
             "grounding_feedback": None, "usage": None, "latency_s": None}
    signals = fx.extract_signals(state)["signals"]
    assert signals is not None and signals.risks, "no risks extracted to judge"


    entailment = GEval(
        name="Citation entailment",
        criteria=("Given INPUT (a verbatim quote from a customer's communications) and "
                  "ACTUAL_OUTPUT (a claim an analyst made), decide whether the quote directly "
                  "SUPPORTS the claim. Penalise claims that go beyond or contradict the quote."),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.7,
    )


    top = max(signals.risks, key=lambda f: f.confidence)
    quote = top.evidence[0].quote if top.evidence else ""
    case = LLMTestCase(input=quote, actual_output=top.summary)
    entailment.measure(case)
    assert entailment.score is not None and entailment.score >= 0.7, entailment.reason