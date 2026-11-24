# ruff: noqa: E501
"""Persistence helpers so the report endpoint has what it reads (diagnosis payload, patch, runs).

`diagnosed_payload` is the DIAGNOSED transition payload (keys the report builder reads: evidence_ids,
target, symptom_evidence_ids, hypotheses, model_usage). `save_outcome` writes the incident's
cause_class/base_sha, the frozen Patch (with code-graph impact) and ValidationRun rows. Nothing here
touches the repo or lab: the patch only exists as text in the database.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from traceforge.contracts.test_run import TestRunRequest, TestRunResult
from traceforge.incidents import repository as incidents
from traceforge.incidents.models import AuditEvent, Incident
from traceforge.repair import RepairResult
from traceforge.repair.models import Patch, ValidationRun
from traceforge.repair.repository import add_patch, add_validation_run

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+", re.M)
DIFF_PATH = re.compile(r"^\+\+\+ b/(.+)$", re.M)


def diagnosed_payload(diagnosis: Any, submitted: Any, usage: Any) -> dict[str, Any]:
    """Payload of DIAGNOSED. `symptom_evidence_ids` is not produced by the agent (left empty)."""
    return {
        "evidence_ids": diagnosis.evidence_ids,
        "target": diagnosis.target,
        "cause_class": diagnosis.cause_class,
        "symptom_evidence_ids": [],
        "hypotheses": [
            {
                "cause_class": diagnosis.cause_class,
                "target": diagnosis.target,
                "supporting_ids": diagnosis.evidence_ids,
                "contradicting_ids": diagnosis.contradicting_ids,
            }
        ],
        "rationale": getattr(submitted, "rationale", None),
        # pipeline v5 fields (None for the formal v4 diagnosis, which does not produce them)
        "confidence": getattr(submitted, "confidence", None),
        "observed_symptom": getattr(submitted, "observed_symptom", None),
        "reconciliation": getattr(submitted, "reconciliation", None),
        "sufficient_evidence": getattr(submitted, "sufficient_evidence", None),
        "model_usage": {
            "provider": usage.provider,
            "model": usage.model,
            "tokens_in": usage.tokens_in,
            "tokens_out": usage.tokens_out,
            "latency_ms": round(usage.latency_ms),
            "cache_hits": usage.cache_hits,
            "list_price_usd": usage.list_price_usd,
            "note": "diagnosis stage only (patch-stage usage is in the run record)",
        },
    }


@dataclass
class RunLog:
    """Records every sandbox call so ValidationRun rows can be written afterwards."""

    run_tests: Any
    calls: list[tuple[str, TestRunResult]] = field(default_factory=list)

    def __call__(self, req: TestRunRequest) -> TestRunResult:
        res = self.run_tests(req)
        self.calls.append((req.suite, res))
        return res

    def rows(self) -> list[tuple[int, str, TestRunResult]]:
        """(attempt, suite, result): baseline reproducer = 0, then reproducer+visible per attempt,
        hidden on the frozen patch (last attempt number)."""
        out, attempt, seen_base = [], 0, False
        for suite, res in self.calls:
            if suite == "reproducer" and not seen_base:
                seen_base = True
            elif suite == "reproducer":
                attempt += 1
            elif suite == "hidden":
                attempt = max(attempt, 1)
            out.append((attempt, suite, res))
        return out


def _changed_nodes(graph: Any, diff: str) -> list[str]:
    paths = DIFF_PATH.findall(diff)
    out = []
    for nid, d in graph.nx.nodes(data=True):
        if (
            d.get("kind") in ("function", "method", "class", "settings_field")
            and d.get("path") in paths
        ):
            for m in HUNK.finditer(diff):
                a = int(m.group(1))
                b = a + int(m.group(2) or 1) - 1
                if d["start"] <= b and a <= d["end"]:
                    out.append(nid)
                    break
    return sorted(out)


def impact_of(graph: Any, diff: str, signature_changed: bool) -> list[dict]:
    """[{"symbol": changed node, "impacted": [dependent nodes]}] from the code graph (base tree)."""
    from traceforge.codeintel.queries import impact_set

    rows = []
    for nid in _changed_nodes(graph, diff):
        sig = {nid} if signature_changed else set()
        rows.append({"symbol": nid, "impacted": impact_set(graph, [nid], sig).symbols[:50]})
    return rows


def save_outcome(
    db: Session,
    inc: Incident,
    *,
    cause_class: str,
    base_sha: str,
    rr: RepairResult | None,
    runlog: RunLog | None,
    graph: Any = None,
) -> None:
    inc.cause_class, inc.base_sha = cause_class, base_sha
    if rr is not None and rr.diff and rr.patch_sha256:
        impact = impact_of(graph, rr.diff, rr.signature_changed) if graph is not None else []
        add_patch(
            db,
            Patch(
                incident_id=inc.id,
                diff=rr.diff,
                sha256=rr.patch_sha256,
                paths=sorted(set(DIFF_PATH.findall(rr.diff))),
                signature_changed=rr.signature_changed,
                impact=impact,
            ),
        )
    for attempt, suite, res in runlog.rows() if runlog else []:
        outcome = "timeout" if res.timed_out else ("error" if res.error else (
            "passed" if res.failed == 0 and res.passed > 0 else "failed"))  # fmt: skip
        add_validation_run(
            db,
            ValidationRun(
                incident_id=inc.id,
                attempt=attempt,
                suite=suite,
                passed=res.passed,
                failed=res.failed,
                outcome=outcome,
                tests=[t.model_dump() for t in res.tests],
            ),
        )
    db.commit()


EXPECTED_KINDS = {
    "log": "application logs of the failing service",
    "config": "the service configuration (settings values)",
    "trace_frame": "a stack trace or failing frame",
    "health": "dependency health checks",
}


def missing_evidence_for(evidence: Any, reason: str | None = None) -> list[str]:
    """Deterministic list of what the evidence bundle lacked (no model text, no guessing)."""
    present = {i.kind for i in getattr(evidence, "items", [])}
    out = [
        f"No {k} evidence collected: {why}" for k, why in EXPECTED_KINDS.items() if k not in present
    ]
    if not out:
        out.append(
            "The collected evidence did not tie any code or config target to the symptom"
            + (f" ({reason})" if reason else "")
        )
    return out


def record_missing_evidence(
    db: Session, inc: Incident, evidence: Any, reason: str | None
) -> list[str]:
    """Persist `missing_evidence` for an inconclusive incident as an audit event that the report
    builder reads (the INCONCLUSIVE transition payload is written by agent/pipeline.py)."""
    missing = missing_evidence_for(evidence, reason)
    payload = {"missing_evidence": missing, "reason": reason}
    incidents.add_event(
        db,
        AuditEvent(
            incident_id=inc.id,
            actor="agent",
            event_type="missing_evidence",
            from_state=inc.state,
            to_state=None,
            payload=payload,
            payload_sha256=hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()
            ).hexdigest(),
        ),
    )
    db.commit()
    return missing
