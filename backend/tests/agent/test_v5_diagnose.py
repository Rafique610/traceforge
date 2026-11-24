# ruff: noqa: E501
"""Pipeline v5 diagnosis: prompt, structured output, claim validation, tool budget, discovery.

The over-long rationales are the three real final submissions recorded in the LLM cache for
shop_api-015/016/022 (rejected by the 600-character cap, which exhausted the budget in v4).
"""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace as N

import pytest
from agentfakes import FakeChat, call, resp
from v5helpers import bundle, item

from traceforge.agent import diagnose as dz
from traceforge.agent import symptom
from traceforge.agent.diagnose import Usage, diagnose
from traceforge.agent.pipeline import Sources, run_case
from traceforge.agent.tools import (
    SubmitDiagnosis,
    SubmitDiagnosisV2,
    ToolContext,
    ToolError,
    dispatch,
    tool_schemas,
)
from traceforge.contracts.context import ContextBundle, ContextHit
from traceforge.contracts.test_run import TestOutcome, TestRunResult
from traceforge.retrieval import RealContextSource

FIX = Path(__file__).parent / "fixtures"
OVERLONG = json.loads((FIX / "overlong_rationales.json").read_text("utf-8"))
CASE = N(service="shop_api", case_id="shop_api-010")
SYMPTOM_OUT = (
    "F\n=== FAILURES ===\n___ test_price_1 ___\n/reproducer/test_symptom.py:7: in test_price_1\n"
    "    assert observe_price(c, s, [('7.45', 1)], 'staff50') == [200, '11.10']\n"
    "E   AssertionError: assert [200, '9.35'] == [200, '11.10']\n"
    'INFO httpx HTTP Request: GET http://testserver/orders/1/quote?coupon=staff50 "HTTP/1.1 200 OK"\n'
)
SYM_RUN = TestRunResult(
    passed=0,
    failed=1,
    tests=[TestOutcome(id="test_symptom.py::test_price_1", outcome="failed")],
    stdout_tail=SYMPTOM_OUT,
    duration_ms=1,
    timed_out=False,
)


class FakeCtx:
    """Minimal ContextSource: one known symbol, search, index; records nothing hidden."""

    SYMBOLS = {("lab/shop_api/app/coupons.py", "discount_pct"): "32: def discount_pct(...)"}

    def retrieve(self, evidence, graph, mode, token_budget):
        hit = ContextHit(
            node_id="sym:lab/shop_api/app/coupons.py::discount_pct",
            kind="symbol",
            path="lab/shop_api/app/coupons.py",
            start_line=32,
            end_line=39,
            score=0.5,
            reasons=["bm25:1.00"],
            excerpt="def discount_pct(code, cap): ...",
        )
        return ContextBundle(
            incident_id="i", mode=mode, token_budget=token_budget, tokens_used=1, hits=[hit]
        )

    def read_symbol(self, case, path, qualname):
        return self.SYMBOLS.get((path, qualname))

    def neighbors(self, node_id):
        return []

    def search_code(self, case, query, limit=8):
        return ["lab/shop_api/app/coupons.py::discount_pct (lines 32-39)"][:limit]

    def workspace_index(self, case):
        return "lab/shop_api/app/coupons.py: parse_codes, discount_pct, apply_discount"


def evidence(with_symptom=True):
    base = bundle(
        item(1, "health", "/health -> 200 ok"),
        item(2, "config", "settings.db_host [str] = 'localhost'", path="lab/shop_api/app/settings.py", line=14),
        item(3, "compose", "service shop_api environment: DB_HOST=lab_db", path="lab/compose.yaml", line=40),
        item(4, "config", "settings.max_discount_pct [int] = 30", path="lab/shop_api/app/settings.py", line=26),
    )  # fmt: skip
    return (
        symptom.with_symptom(base, symptom.build_symptom({"reproducer": SYM_RUN}))
        if with_symptom
        else base
    )


def tc(ev=None, v5=True):
    return ToolContext(CASE, ev or evidence(), FakeCtx(), v5=v5)


CODE = dict(
    cause_class="application_code",
    path="lab/shop_api/app/coupons.py",
    qualname="discount_pct",
    supporting_evidence_ids=["EV-0005"],
    observed_symptom="a staff50 coupon quote returns 9.35 instead of 11.10",
    rationale="discount_pct returns the raw percentage without applying the cap",
    confidence="medium",
)


def run_diag(*script, v5=True, ev=None):
    chat, usage = FakeChat(*script), Usage()
    ctx = FakeCtx().retrieve(None, None, "L", 3000)
    r = diagnose(tc(ev, v5), ctx, chat, usage, 12000, "v5" if v5 else "v4")
    return r, chat


# --- prompt -----------------------------------------------------------------------------------


def test_prompt_contains_the_symptom_labels_index_and_no_placeholders():
    r, chat = run_diag(resp(call("submit_diagnosis", cause_class="insufficient_evidence")))
    system, user = chat.messages[0][0]["content"], chat.messages[0][1]["content"]
    assert (
        "<symptom>" in user
        and "request made by the test: GET /orders/1/quote?coupon=staff50" in user
    )
    assert "static/declared" in user and "lab/shop_api/app/settings.py:14" in user
    assert "Evidence labels:" in user and "NOT what the running service uses" in user
    assert "lab/shop_api/app/coupons.py: parse_codes, discount_pct" in user  # workspace index
    assert not any(p in user for p in ("{symptom}", "{evidence}", "{files}", "{context}"))
    assert "at most 500 characters" in system and "search_code" in system
    names = [t["function"]["name"] for t in chat.tools[0]]
    assert "search_code" in names and r.failure_reason == "insufficient_evidence"


def test_symptom_section_says_so_when_no_test_failed():
    _, chat = run_diag(
        resp(call("submit_diagnosis", cause_class="insufficient_evidence")), ev=evidence(False)
    )
    assert dz.NO_SYMPTOM in chat.messages[0][1]["content"]


def test_v4_prompt_and_tools_are_unchanged():
    r, chat = run_diag(
        resp(call("submit_diagnosis", cause_class="insufficient_evidence")), v5=False
    )
    user = chat.messages[0][1]["content"]
    assert "<symptom>" not in user and "static/declared" not in user
    assert [t["function"]["name"] for t in chat.tools[0]] == [
        "read_evidence", "read_symbol", "get_neighbors", "submit_diagnosis",
    ]  # fmt: skip
    assert len(tool_schemas()) == 4 and len(tool_schemas(True)) == 5


# --- structured output and over-long text -----------------------------------------------------


@pytest.mark.parametrize("cid", sorted(OVERLONG))
def test_recorded_overlong_rationales_are_rejected_locally_with_a_useful_error(cid):
    with pytest.raises(ToolError) as e:
        dispatch("submit_diagnosis", OVERLONG[cid], tc())
    assert e.value.schema and "string_too_long" in str(e.value) and "rationale" in str(e.value)


@pytest.mark.parametrize("cid", sorted(OVERLONG))
def test_v5_rejected_submission_does_not_consume_a_tool_call_and_can_be_corrected(cid):
    good = call("submit_diagnosis", **CODE)
    bad = type(good)(name="submit_diagnosis", arguments=OVERLONG[cid])
    r, chat = run_diag(resp(bad), resp(good))
    assert (
        r.failure_reason is None
        and r.diagnosis.target == "lab/shop_api/app/coupons.py::discount_pct"
    )
    assert (
        r.tool_calls == 1 and r.rejected == 1 and r.invalid_tool_calls == 1
    )  # only the valid call counts
    assert "does not count toward your tool budget" in chat.messages[1][-1]["content"]


def test_v4_still_counts_the_rejected_submission_as_before():
    bad = call("submit_diagnosis", cause_class="configuration", rationale="x" * 700)
    r, _ = run_diag(resp(bad), *[resp(bad)] * 6, v5=False)
    assert (
        r.failure_reason == "budget_exhausted" and r.tool_calls == 6
    )  # the old defect, preserved for v4


def test_repeated_identical_invalid_output_stops_as_invalid_output_not_budget():
    bad = call("submit_diagnosis", cause_class="configuration", rationale="x" * 700)
    r, chat = run_diag(resp(bad), resp(bad))
    assert r.failure_reason == "invalid_output" and r.submitted is None and r.diagnosis.abstained
    assert chat.n == 2  # stopped at the second identical rejection, no further requests


def test_rejection_cap_then_invalid_output():
    bads = [
        call("submit_diagnosis", cause_class="configuration", rationale="y" * (700 + i))
        for i in range(5)
    ]
    r, chat = run_diag(*[resp(b) for b in bads])
    assert (
        r.failure_reason == "invalid_output"
        and r.rejected == dz.MAX_REJECTED + 1
        and r.tool_calls == 0
    )


def test_three_failure_reasons_stay_distinct():
    abstain, _ = run_diag(resp(call("submit_diagnosis", cause_class="insufficient_evidence")))
    reads = [resp(call("read_evidence", evidence_id="EV-0001")) for _ in range(dz.TOOL_BUDGET_V5)]
    exhausted, _ = run_diag(*reads)
    bad = call("submit_diagnosis", cause_class="configuration", rationale="z" * 700)
    invalid, _ = run_diag(resp(bad), resp(bad))
    assert (abstain.failure_reason, exhausted.failure_reason, invalid.failure_reason) == (
        "insufficient_evidence", "budget_exhausted", "invalid_output",
    )  # fmt: skip


def test_last_call_is_flagged_so_the_model_submits_instead_of_running_out():
    reads = [
        resp(call("read_evidence", evidence_id="EV-0001")) for _ in range(dz.TOOL_BUDGET_V5 - 1)
    ]
    _, chat = run_diag(*reads, resp(call("submit_diagnosis", cause_class="insufficient_evidence")))
    assert "1 tool call left" in chat.messages[-1][-1]["content"]


def test_v2_schema_requires_symptom_confidence_and_reconciliation():
    base = dict(CODE)
    SubmitDiagnosisV2(**base)  # valid
    with pytest.raises(ValueError, match="observed symptom"):
        SubmitDiagnosisV2(**{**base, "observed_symptom": ""})
    with pytest.raises(ValueError, match="reconciliation"):
        SubmitDiagnosisV2(**{**base, "contradicting_evidence_ids": ["EV-0001"]})
    SubmitDiagnosisV2(**{**base, "contradicting_evidence_ids": ["EV-0001"],
                         "reconciliation": "health is ok because the fault only affects quotes"})  # fmt: skip
    with pytest.raises(ValueError, match="sufficient_evidence"):
        SubmitDiagnosisV2(**{**base, "sufficient_evidence": False})
    with pytest.raises(ValueError):
        SubmitDiagnosisV2(**{**base, "rationale": "r" * 501})
    assert isinstance(SubmitDiagnosisV2(**base), SubmitDiagnosis)


# --- claim validation -------------------------------------------------------------------------


def test_a_diagnosis_that_ignores_the_symptom_is_rejected():
    cfg = dict(
        cause_class="configuration", config_key="shop_api.DB_HOST",
        supporting_evidence_ids=["EV-0002", "EV-0003"], contradicting_evidence_ids=["EV-0001"],
        observed_symptom="settings default is localhost but compose says lab_db",
        reconciliation="health ok may come from a different process than the settings object",
        rationale="env not applied",
    )  # fmt: skip
    with pytest.raises(ToolError, match="explain the observed symptom"):
        dispatch("submit_diagnosis", json.dumps(cfg), tc())
    ok = dict(cfg, supporting_evidence_ids=[*cfg["supporting_evidence_ids"], "EV-0005"])
    assert dispatch("submit_diagnosis", json.dumps(ok), tc()).config_key == "shop_api.DB_HOST"


def test_contradicting_evidence_must_be_reconciled():
    cfg = dict(CODE, contradicting_evidence_ids=["EV-0001"])
    with pytest.raises(ToolError, match="reconciliation"):
        dispatch("submit_diagnosis", json.dumps(cfg), tc())


def test_config_key_must_appear_in_the_evidence_and_in_the_cited_items():
    base = dict(
        CODE,
        cause_class="configuration",
        config_key="shop_api.NO_SUCH_KEY",
        path=None,
        qualname=None,
    )
    with pytest.raises(ToolError, match="appears in no evidence"):
        dispatch("submit_diagnosis", json.dumps(base), tc())
    elsewhere = dict(
        base, config_key="shop_api.MAX_DISCOUNT_PCT", supporting_evidence_ids=["EV-0005"]
    )
    with pytest.raises(ToolError, match="none of your supporting evidence mentions"):
        dispatch("submit_diagnosis", json.dumps(elsewhere), tc())
    ok = dict(elsewhere, supporting_evidence_ids=["EV-0005", "EV-0004"])
    assert dispatch("submit_diagnosis", json.dumps(ok), tc()).qualified_target("shop_api")


def test_unknown_evidence_id_and_missing_symbol_are_rejected_with_suggestions():
    with pytest.raises(ToolError, match="unknown evidence ids"):
        dispatch(
            "submit_diagnosis", json.dumps(dict(CODE, supporting_evidence_ids=["EV-0099"])), tc()
        )
    missing = dict(CODE, qualname="nope")
    with pytest.raises(ToolError, match="does not exist.*did you mean.*discount_pct"):
        dispatch("submit_diagnosis", json.dumps(missing), tc())


def test_abstention_needs_no_symptom_and_is_accepted():
    out = dispatch("submit_diagnosis", json.dumps(dict(cause_class="insufficient_evidence")), tc())
    assert out.cause_class == "insufficient_evidence"


def test_a_valid_code_diagnosis_is_accepted_and_recorded_with_its_fields():
    r, _ = run_diag(resp(call("submit_diagnosis", **CODE)))
    assert r.failure_reason is None and not r.diagnosis.abstained
    assert (
        r.submitted.observed_symptom.startswith("a staff50") and r.submitted.confidence == "medium"
    )


# --- discovery --------------------------------------------------------------------------------


def test_search_code_tool_and_read_symbol_suggestions_in_v5_only():
    out = dispatch("search_code", json.dumps({"query": "coupon discount"}), tc())
    assert "coupons.py::discount_pct" in out
    with pytest.raises(ToolError, match="did you mean"):
        dispatch(
            "read_symbol",
            json.dumps({"path": "lab/shop_api/app/coupons.py", "qualname": "x"}),
            tc(),
        )
    with pytest.raises(ToolError) as e:
        dispatch(
            "read_symbol",
            json.dumps({"path": "lab/shop_api/app/coupons.py", "qualname": "x"}),
            tc(v5=False),
        )
    assert str(e.value) == "symbol not found"  # v4 message unchanged


def test_discovery_stays_inside_the_service_workspace(tmp_path):
    lab = Path(__file__).resolve().parents[3] / "lab"
    if not lab.is_dir():
        pytest.skip("lab/ not present")
    root = tmp_path / "tree"
    shutil.copytree(lab, root / "lab", ignore=shutil.ignore_patterns("__pycache__", ".env"))
    (root / "datasets" / "hidden_tests" / "c1").mkdir(parents=True)
    (root / "datasets" / "hidden_tests" / "c1" / "test_h.py").write_text(
        "def test_hidden_only(): pass\n"
    )
    src = RealContextSource(root)
    case = N(service="shop_api", case_id="c1")
    index = src.workspace_index(case)
    hits = src.search_code(case, "coupon discount test retry worker hidden", 20)
    for text in (index, "\n".join(hits)):
        assert "/tests/" not in text and "lab/worker/" not in text and "hidden" not in text
    assert "lab/shop_api/app/coupons.py: " in index and "discount_pct" in index
    assert src.read_symbol(case, "datasets/hidden_tests/c1/test_h.py", "test_hidden_only") is None
    tcx = ToolContext(case, evidence(), src, v5=True)
    with pytest.raises(ToolError, match="path not allowed"):
        dispatch("read_symbol", json.dumps({"path": "lab/worker/queue.py", "qualname": "x"}), tcx)


# --- end to end through the pipeline ----------------------------------------------------------


class _Cases:
    sha256 = "0" * 64

    def get(self, _):
        from traceforge.agent.sources import SampleCaseSource

        return SampleCaseSource().get("config").model_copy(update={"service": "shop_api"})


class _Evidence:
    def collect(self, incident_id, service, case):
        return evidence(False).model_copy(update={"incident_id": incident_id})


def test_run_case_v5_sends_the_symptom_records_the_version_and_can_stop_after_diagnosis():
    chat = FakeChat(resp(call("submit_diagnosis", **CODE)))
    sym = symptom.build_symptom({"reproducer": SYM_RUN})
    art = {}
    rec = run_case(
        _Cases().get("x"), "G0", Sources(_Cases(), _Evidence(), FakeCtx()), chat_fn=chat,
        pipeline="v5", symptom=sym, diagnose_only=True, artifacts=art,
    )  # fmt: skip
    assert chat.n == 1 and "request made by the test" in chat.messages[0][1]["content"]
    assert (
        rec.pipeline_version == "v5"
        and rec.outcome == "NO_PATCH"
        and rec.failure_reason == "diagnosis_only"
    )
    assert rec.diagnosis.target == "lab/shop_api/app/coupons.py::discount_pct" and rec.attempts == 0
    ids = [i.id for i in art["evidence"].items]
    assert ids[:4] == ["EV-0001", "EV-0002", "EV-0003", "EV-0004"] and len(ids) > 4  # appended


def test_v5_prompt_hash_differs_from_v4_and_v4_is_unchanged():
    from traceforge.agent import prompting

    assert prompting.prompt_hash("v4") != prompting.prompt_hash("v5")
    assert prompting.prompt_hash() == prompting.prompt_hash("v4")


def test_a_blocked_symptom_is_never_sent():
    sym = symptom.build_symptom({"reproducer": SYM_RUN})
    sym.status = "blocked: hidden_marker"
    chat = FakeChat(resp(call("submit_diagnosis", cause_class="insufficient_evidence")))
    run_case(_Cases().get("x"), "L0", Sources(_Cases(), _Evidence(), FakeCtx()), chat_fn=chat,
             pipeline="v5", symptom=sym, diagnose_only=True)  # fmt: skip
    user = chat.messages[0][1]["content"]
    assert "staff50" not in user and dz.NO_SYMPTOM in user


def test_handoff_abstains_when_the_target_stops_being_justified_and_requests_no_patch():
    class Flaky(FakeCtx):
        calls = 0

        def read_symbol(self, case, path, qualname):
            Flaky.calls += 1
            return super().read_symbol(case, path, qualname) if Flaky.calls == 1 else None

    chat = FakeChat(resp(call("submit_diagnosis", **CODE)))
    sym = symptom.build_symptom({"reproducer": SYM_RUN})
    rec = run_case(
        _Cases().get("x"), "G0", Sources(_Cases(), _Evidence(), Flaky()), chat_fn=chat,
        pipeline="v5", symptom=sym,
    )  # fmt: skip
    assert chat.n == 1  # no patch request was made
    assert rec.diagnosis.abstained and rec.outcome == "NO_PATCH"
    assert rec.failure_reason == "unsupported_target: symbol not found"


def test_rejected_calls_keep_their_error_text_in_the_trace_for_audit():
    good = call("submit_diagnosis", **CODE)
    bad = call("submit_diagnosis", cause_class="configuration", rationale="x" * 700)
    r, _ = run_diag(resp(bad), resp(good))
    rejected = [t for t in r.trace if t.get("rejected")]
    assert len(rejected) == 1 and "string_too_long" in rejected[0]["error"]
    assert all("error" not in t for t in r.trace if t["ok"])


def test_v5_stops_at_the_first_provider_failure_while_v4_keeps_its_tolerance():
    from traceforge.agent.gateway import GatewayError

    down = GatewayError("axforge call failed (429): RateLimitError; not retried")
    r5, chat5 = run_diag(down, down, down)
    assert chat5.n == 1 and r5.failure_reason.startswith("provider_error")  # one request only
    r4, chat4 = run_diag(down, down, down, v5=False)
    assert chat4.n == 3 and r4.failure_reason.startswith("provider_error")  # formal behaviour kept


def test_run_case_from_a_saved_diagnosis_asks_no_diagnose_request_and_records_patch_tokens_only():
    from traceforge.agent.tools import SubmitDiagnosisV2

    saved = SubmitDiagnosisV2(**CODE)
    edit = "<<<<<<< SEARCH lab/shop_api/app/coupons.py\nold\n=======\nnew\n>>>>>>> REPLACE"
    chat = FakeChat(resp(content=edit))
    art = {}
    rec = run_case(
        _Cases().get("x"), "G0", Sources(_Cases(), _Evidence(), FakeCtx()), chat_fn=chat,
        pipeline="v5", saved=(saved, evidence(True)), artifacts=art,
    )  # fmt: skip
    assert chat.n == 1 and chat.messages[0][0]["content"].startswith("You are the patch stage")
    assert chat.tools[0] is None  # the patch stage has no tools: no diagnose request was made
    assert rec.tool_calls == 0 and rec.invalid_tool_calls == 0
    assert (rec.tokens_in, rec.tokens_out) == (100, 10)  # the patch request only
    assert (
        rec.diagnosis.target == "lab/shop_api/app/coupons.py::discount_pct"
        and not rec.diagnosis.abstained
    )
    assert rec.pipeline_version == "v5" and art["submitted"] is saved  # the saved object, unchanged


def test_a_saved_diagnosis_is_refused_outside_pipeline_v5():
    from traceforge.agent.tools import SubmitDiagnosisV2

    with pytest.raises(ValueError, match="only be used with pipeline v5"):
        run_case(_Cases().get("x"), "L0", Sources(_Cases(), _Evidence(), FakeCtx()),
                 chat_fn=FakeChat(), saved=(SubmitDiagnosisV2(**CODE), evidence(True)))  # fmt: skip


# --- validation gaps: observed support, runtime_dependency, class/target mismatch ---------------


def test_a_diagnosis_resting_only_on_static_declarations_is_rejected_when_no_symptom_exists():
    ev = evidence(with_symptom=False)
    cfg = dict(
        CODE,
        cause_class="configuration",
        config_key="shop_api.MAX_DISCOUNT_PCT",
        path=None,
        qualname=None,
        supporting_evidence_ids=["EV-0004"],
    )
    with pytest.raises(ToolError, match="observed item"):
        dispatch("submit_diagnosis", json.dumps(cfg), tc(ev))
    ok = dict(cfg, supporting_evidence_ids=["EV-0004", "EV-0001"])
    assert dispatch("submit_diagnosis", json.dumps(ok), tc(ev))


def test_a_finding_is_not_observed_support():
    from traceforge.diagnostics import findings_as_items, run_rules  # noqa: F401
    from traceforge.diagnostics.rules import Finding

    ev = evidence(with_symptom=False)
    fi = findings_as_items(ev, [Finding("r", "a hint about max_discount_pct", ("EV-0004",))])
    ev = ev.model_copy(update={"items": [*ev.items, *fi]})
    cfg = dict(
        CODE,
        cause_class="configuration",
        config_key="shop_api.MAX_DISCOUNT_PCT",
        path=None,
        qualname=None,
        supporting_evidence_ids=["EV-0004", fi[0].id],
    )
    with pytest.raises(ToolError, match="observed item"):
        dispatch("submit_diagnosis", json.dumps(cfg), tc(ev))


def test_runtime_dependency_must_cite_a_runtime_item_and_class_must_match_target():
    ev = evidence(with_symptom=False)
    dep = dict(
        cause_class="runtime_dependency",
        supporting_evidence_ids=["EV-0004"],
        observed_symptom="the broker container is not running",
        rationale="x",
    )
    with pytest.raises(ToolError, match="observed item"):
        dispatch("submit_diagnosis", json.dumps(dep), tc(ev))
    ok = dict(dep, supporting_evidence_ids=["EV-0001"])
    assert dispatch("submit_diagnosis", json.dumps(ok), tc(ev))
    wrong = dict(CODE, config_key="shop_api.MAX_DISCOUNT_PCT", path=None, qualname=None)
    with pytest.raises(ToolError, match="use cause_class configuration"):
        dispatch("submit_diagnosis", json.dumps(wrong), tc())


def test_v5_config_targets_are_canonical_while_v4_is_unchanged():
    base = dict(
        cause_class="configuration",
        supporting_evidence_ids=["EV-0001"],
        observed_symptom="a wrong delay",
        rationale="r",
    )
    for given, want in (
        ("backoff_base_s", "worker.BACKOFF_BASE_S"),
        ("worker.backoff_base_s", "worker.BACKOFF_BASE_S"),
        ("shop_api.REDIS_HOST", "shop_api.REDIS_HOST"),
    ):
        assert SubmitDiagnosisV2(**base, config_key=given).qualified_target("worker") == want
    from traceforge.agent.tools import SubmitDiagnosis

    assert (
        SubmitDiagnosis(
            cause_class="configuration",
            config_key="backoff_base_s",
            supporting_evidence_ids=["EV-0001"],
        ).qualified_target("worker")
        == "worker.backoff_base_s"
    )  # v4 as before
