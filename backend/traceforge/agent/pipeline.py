"""run_case: collect -> retrieve -> diagnose -> patch, producing an AgentRunRecord."""

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from sqlalchemy.orm import Session

from traceforge.agent import gateway, prompting
from traceforge.agent.diagnose import ChatFn, DiagnoseResult, Usage, diagnose
from traceforge.agent.patch import request_patch
from traceforge.agent.persist import diagnosed_payload
from traceforge.agent.sources import (
    CaseSource,
    ContextSource,
    EvidenceSource,
    SampleCaseSource,
    SampleContextSource,
    SampleEvidenceSource,
)
from traceforge.agent.tools import SubmitDiagnosis, ToolContext
from traceforge.config import Settings, get_settings
from traceforge.contracts.agent_run import AgentRunRecord, Diagnosis
from traceforge.contracts.case_manifest import REPAIRABLE, CaseManifest
from traceforge.incidents import repository, service
from traceforge.incidents.models import Incident
from traceforge.incidents.states import State
from traceforge.repair import RepairResult

PRE = [State.SNAPSHOT_LOCKED, State.EVIDENCE_COLLECTED, State.CONTEXT_RETRIEVED]
ORDER = [State.CREATED, *PRE, State.DIAGNOSED, State.PATCH_PROPOSED, State.REVIEW_PENDING]


RepairFn = Callable[[ToolContext, SubmitDiagnosis, ChatFn, Usage], RepairResult]


@dataclass
class Sources:
    cases: CaseSource
    evidence: EvidenceSource
    context: ContextSource


def sample_sources() -> Sources:
    return Sources(SampleCaseSource(), SampleEvidenceSource(), SampleContextSource())


def _case_hash(case: CaseManifest) -> str:
    return hashlib.sha256(case.model_dump_json().encode()).hexdigest()


def _ranked(ctx: Any, limit: int = 10) -> list[dict]:
    """Top hits with the reasons they were retrieved (no source text), for the audit view."""
    return [
        {
            "path": h.path,
            "kind": h.kind,
            "start_line": h.start_line,
            "end_line": h.end_line,
            "score": round(h.score, 4),
            "reasons": list(h.reasons),
        }
        for h in ctx.hits[:limit]
    ]


def _move(db: Session | None, inc: Incident | None, to: State, actor: str, payload=None) -> None:
    """Advance the incident (if any) to `to`, skipping states it has already passed."""
    if db is None or inc is None:
        return
    if to in ORDER and inc.state in ORDER and ORDER.index(inc.state) >= ORDER.index(to):
        return
    service.transition(db, inc.id, to, actor, payload)


def _move_repair(db: Session | None, inc: Incident | None, rr: RepairResult) -> None:
    if rr.diff:
        _move(db, inc, State.PATCH_PROPOSED, "agent", {"patch_sha256": rr.patch_sha256})
        _move(db, inc, State.VALIDATING, "system")
        verified = rr.outcome == "TEST_VERIFIED_IN_LAB"
        _move(
            db,
            inc,
            State.VERIFIED if verified else State.UNVERIFIED,
            "system",
            rr.transition_payload(),
        )
    _move(db, inc, State.REVIEW_PENDING, "agent", {"reason": rr.reason, "outcome": rr.outcome})


def run_case(
    case_or_incident: CaseManifest | Incident,
    condition: str,
    sources: Sources | None = None,
    *,
    db: Session | None = None,
    settings: Settings | None = None,
    chat_fn: ChatFn | None = None,
    replicate: int = 0,
    dataset_sha256: str | None = None,
    artifacts: dict | None = None,
    repair: RepairFn | None = None,
    pipeline: str = "v4",
    symptom: Any = None,
    diagnose_only: bool = False,
    saved: tuple | None = None,
) -> AgentRunRecord:
    """Run one case under L0/G0/L1/G1 (retrieval L|G x feedback F0|F1). Needs `db` for incidents.

    Without `repair`, one patch request is made (outcome UNVERIFIED). With `repair` (see
    agent/repair_run.py) the repair loop runs and its RepairResult sets the record fields.
    `artifacts`, if given, is filled with `diff`, `submitted` (the diagnosis) and `trace`.

    `saved` = (diagnosis, evidence) from an earlier diagnosis run (pipeline v5 only): the saved
    diagnosis and the exact evidence it was made on are used as they are; no evidence collection,
    retrieval or diagnose request happens; the record's tokens are those of the patch stage only.
    """
    s, src = settings or get_settings(), sources or sample_sources()
    t0 = time.monotonic()
    inc = case_or_incident if isinstance(case_or_incident, Incident) else None
    case = src.cases.get(inc.case_id) if inc else case_or_incident
    incident_id = str(inc.id) if inc else f"inc-{case.case_id}"
    chat_fn = chat_fn or partial(
        gateway.chat, settings=s, replicate_index=replicate, seed=0, temperature=0.0
    )
    budget = getattr(s, "agent_context_budget_chars", prompting.DEFAULT_CONTEXT_BUDGET_CHARS)

    _move(db, inc, State.SNAPSHOT_LOCKED, "system", {"base_sha": case.base_sha})
    v5 = pipeline == "v5"
    if saved is not None and not v5:
        raise ValueError("a saved diagnosis can only be used with pipeline v5")
    evidence = (
        saved[1] if saved is not None else src.evidence.collect(incident_id, case.service, case)
    )
    if saved is None and db is not None and inc is not None:
        if not repository.list_evidence(db, inc.id):
            repository.save_evidence_bundle(db, evidence)
            db.commit()
    if saved is None and v5 and symptom is not None and symptom.status in ("ok", "no_failure"):
        from traceforge.agent.symptom import with_symptom

        evidence = with_symptom(evidence, symptom)  # appended: existing evidence ids unchanged
    _move(db, inc, State.EVIDENCE_COLLECTED, "system", {"items": len(evidence.items)})
    usage, tc = Usage(), ToolContext(case, evidence, src.context, v5=v5)
    if saved is not None:  # the diagnosis is taken as saved: it is not regenerated or changed
        sub = saved[0]
        ctx = None
        reason = saved[2] if len(saved) > 2 else None  # why the source run had no diagnosis
        dr = DiagnoseResult(
            Diagnosis(
                cause_class=sub.cause_class,
                target=None
                if sub.cause_class == "insufficient_evidence"
                else sub.qualified_target(case.service),
                evidence_ids=sub.supporting_evidence_ids,
                contradicting_ids=sub.contradicting_evidence_ids,
                abstained=sub.cause_class == "insufficient_evidence",
            ),
            sub if (sub.cause_class != "insufficient_evidence" or reason is None) else None,
            failure_reason=(reason or "insufficient_evidence")
            if sub.cause_class == "insufficient_evidence"
            else None,
        )
    else:
        ctx = src.context.retrieve(evidence, None, condition[0], budget // 4)
        _move(
            db, inc, State.CONTEXT_RETRIEVED, "system",
            {"hits": len(ctx.hits), "ranked": _ranked(ctx)},
        )  # fmt: skip
        dr = diagnose(tc, ctx, chat_fn, usage, budget, pipeline)
    d = dr.diagnosis
    failure, sha, patched, diff = dr.failure_reason, None, False, None
    outcome, attempts, hidden = None, 0, None
    if artifacts is not None:
        artifacts.update(evidence=evidence, context=ctx, diagnosis_rejected=dr.rejected)
    if not d.abstained and v5:
        from traceforge.agent.handoff import validate_target

        if (
            bad := validate_target(tc, dr.submitted)
        ) is not None:  # never patch an unjustified target
            failure = bad
            d = Diagnosis(cause_class="insufficient_evidence", abstained=True)
    if d.abstained:
        _move(db, inc, State.INCONCLUSIVE, "agent", {"reason": failure})
        _move(db, inc, State.REVIEW_PENDING, "agent", {"reason": failure})
    else:
        _move(db, inc, State.DIAGNOSED, "agent", diagnosed_payload(d, dr.submitted, usage))
        if diagnose_only:
            failure = "diagnosis_only"  # the diagnosis is the result; no patch is requested
        elif d.cause_class in REPAIRABLE:
            patched = True
            if repair is None:
                diff, sha, failure = request_patch(tc, dr.submitted, chat_fn, usage)
                if sha:
                    _move(db, inc, State.PATCH_PROPOSED, "agent", {"patch_sha256": sha})
            else:
                rr = repair(tc, dr.submitted, chat_fn, usage)
                diff, sha, failure = rr.diff, rr.patch_sha256, rr.reason
                outcome, attempts, hidden = rr.outcome, len(rr.attempts), rr.hidden_passed
                _move_repair(db, inc, rr)
        else:
            _move(db, inc, State.REVIEW_PENDING, "agent", {"cause_class": d.cause_class})

    if artifacts is not None:
        artifacts.update(diff=diff, submitted=dr.submitted, trace=dr.trace)
    return AgentRunRecord(
        run_id=f"run-{condition}-{case.case_id}-r{replicate}",
        case_id=case.case_id,
        condition=condition,
        model_id=usage.model or s.llm_model,
        provider=usage.provider or s.llm_provider,
        prompt_hash=prompting.prompt_hash(pipeline),
        pipeline_version=pipeline,
        diagnosis=d,
        patch_sha256=sha,
        attempts=attempts if repair else int(patched),
        outcome=outcome or ("UNVERIFIED" if patched else "NO_PATCH"),
        hidden_passed=hidden,
        tokens_in=usage.tokens_in,
        tokens_out=usage.tokens_out,
        cost_usd=0.0,  # free-only gateway (llm_free_only); nothing is paid
        list_price_usd=usage.list_price_usd,
        latency_ms=int(max(usage.latency_ms, (time.monotonic() - t0) * 1000)),
        tool_calls=dr.tool_calls,
        invalid_tool_calls=dr.invalid_tool_calls,
        cache_hits=usage.cache_hits,
        dataset_sha256=dataset_sha256 or _case_hash(case),
        git_sha=case.base_sha,
        replicate=replicate,
        temperature=0.0,
        seed=0,
        failure_reason=failure,
    )
