"""Builders for hand-made manifests and records (test data only, never presented as real)."""

from traceforge.contracts.agent_run import AgentRunRecord, Diagnosis
from traceforge.contracts.case_manifest import CaseManifest, GoldSymbol

SHA = "a" * 64


def manifest(case_id, cause="configuration", distance=1, keys=(), syms=(), **kw) -> CaseManifest:
    repairable = cause in ("configuration", "application_code")
    return CaseManifest(
        case_id=case_id,
        split="dev",
        cause_class=cause,
        fault_family=kw.pop("fault_family", "fam"),
        service="worker",
        base_sha="b" * 40,
        gold_config_keys=list(keys),
        gold_symbols=[GoldSymbol(path=p, qualname=q, start_line=1, end_line=2) for p, q in syms],
        distance=distance if repairable else None,
        reproducer_id="r",
        hidden_test_ids=["h"] if repairable else [],
        variant_group=case_id,
        **kw,
    )


def record(case_id, cond="L0", cls="configuration", target=None, outcome="NO_PATCH", **kw):
    abstain = cls == "insufficient_evidence"
    diag = Diagnosis(
        cause_class=cls,
        target=None if abstain else target,
        abstained=abstain,
        evidence_ids=[] if abstain else ["EV-0001"],
    )
    base = dict(
        run_id=f"run-{cond}-{case_id}-{kw.get('replicate', 0)}",
        case_id=case_id,
        condition=cond,
        model_id="m",
        provider="p",
        prompt_hash="c" * 64,
        diagnosis=diag,
        attempts=0,
        outcome=outcome,
        tokens_in=10,
        tokens_out=5,
        cost_usd=0.0,
        list_price_usd=0.001,
        latency_ms=1000,
        tool_calls=2,
        invalid_tool_calls=0,
        cache_hits=0,
        dataset_sha256=SHA,
        git_sha="g",
    )
    if outcome == "TEST_VERIFIED_IN_LAB":
        base["hidden_passed"] = True
    base.update(kw)
    return AgentRunRecord(**base)
