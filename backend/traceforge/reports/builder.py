"""Deterministic report from DB records only. No LLM, no network, no filesystem."""

import uuid

from sqlalchemy.orm import Session

from traceforge.incidents import repository as incidents
from traceforge.incidents.models import AuditEvent
from traceforge.incidents.states import State
from traceforge.repair import repository as repair
from traceforge.reports.schemas import (
    EvidenceRef,
    Header,
    Hypothesis,
    OutcomeView,
    PatchView,
    Report,
    ReviewView,
    RootCause,
    ValidationView,
)
from traceforge.reviews import repository as reviews

_VERIFIED = "Verified only by the lab test suites on a snapshot. Not deployed. Review the diff."
_UNVERIFIED = (
    "NOT verified: the cause below is the model's hypothesis and no patch passed the hidden tests. "
    "Not deployed. Treat it as unconfirmed."
)
LIMITATIONS = {
    "configuration": _VERIFIED,
    "application_code": _VERIFIED,
    "runtime_dependency": "A runtime dependency failed; no code patch is proposed.",
    "insufficient_evidence": "Evidence was insufficient to name a cause; no patch is proposed.",
}
DEFAULT_LIMITATION = "No classified cause is stored for this incident. No patch is proposed."


def _limitation(cause: str | None, verified: bool) -> str:
    """Only claim 'verified' when the incident really reached VERIFIED."""
    if cause in ("configuration", "application_code") and not verified:
        return _UNVERIFIED
    return LIMITATIONS.get(cause or "", DEFAULT_LIMITATION)


def _payload(events: list[AuditEvent], state: State) -> dict:
    """Payload of the latest transition into `state` (empty if none)."""
    for e in reversed(events):
        if e.to_state is state and e.event_type == "transition":
            return e.payload or {}
    return {}


MISSING_EVIDENCE_EVENT = "missing_evidence"  # written by agent.persist.record_missing_evidence


def _event_payload(events: list[AuditEvent], event_type: str) -> dict:
    for e in reversed(events):
        if e.event_type == event_type:
            return e.payload or {}
    return {}


def _ids(raw: object, known: set[str]) -> list[str]:
    return [i for i in raw if isinstance(i, str) and i in known] if isinstance(raw, list) else []


def build_report(db: Session, incident_id: uuid.UUID) -> Report | None:
    inc = incidents.get_incident(db, incident_id)
    if inc is None:
        return None
    events = incidents.list_events(db, incident_id)
    items = incidents.list_evidence(db, incident_id)
    known = {i.id for i in items}
    diag = _payload(events, State.DIAGNOSED)
    inconclusive = _payload(events, State.INCONCLUSIVE)
    cause = inc.cause_class

    status = "SUPPORTED" if (cause or diag) else "NOT_DIAGNOSED"
    if cause == "runtime_dependency":
        status = "RUNTIME_DEPENDENCY"
    elif cause == "insufficient_evidence" or (cause is None and inconclusive):
        status = "INCONCLUSIVE"
    ev_ids = _ids(diag.get("evidence_ids"), known)
    target = diag.get("target") if isinstance(diag.get("target"), str) else None

    outcome = OutcomeView(outcome_class=cause)
    if status == "RUNTIME_DEPENDENCY":
        outcome.dependency = target
        outcome.dependency_evidence_ids = ev_ids
    elif status == "INCONCLUSIVE":
        missing = (
            inconclusive.get("missing_evidence")
            or diag.get("missing_evidence")
            or _event_payload(events, MISSING_EVIDENCE_EVENT).get("missing_evidence")
            or []
        )
        outcome.missing_evidence = [m for m in missing if isinstance(m, str)]

    patch = repair.get_patch(db, incident_id)
    review = reviews.get_review(db, incident_id)
    usage = diag.get("model_usage")
    return Report(
        header=Header(
            incident_id=inc.id,
            case_id=inc.case_id,
            service=inc.service,
            base_sha=inc.base_sha,
            origin=inc.source,
            state=inc.state,
            created_at=inc.created_at,
        ),
        symptom=inc.symptom,
        symptom_evidence_ids=_ids(diag.get("symptom_evidence_ids"), known),
        root_cause=RootCause(status=status, cause_class=cause, target=target, evidence_ids=ev_ids),
        outcome=outcome,
        evidence=[
            EvidenceRef(
                id=i.id, kind=i.kind, service=i.service, path=i.path, line=i.line, sha256=i.sha256
            )
            for i in items
        ],
        hypotheses=[
            Hypothesis(
                cause_class=h.get("cause_class"),
                target=h.get("target"),
                supporting_ids=_ids(h.get("supporting_ids"), known),
                contradicting_ids=_ids(h.get("contradicting_ids"), known),
            )
            for h in diag.get("hypotheses", [])
            if isinstance(h, dict)
        ],
        patch=PatchView(
            sha256=patch.sha256,
            paths=patch.paths,
            diff=patch.diff,
            signature_changed=patch.signature_changed,
            impact=patch.impact,
        )
        if patch
        else None,
        validation_runs=[
            ValidationView(
                attempt=r.attempt,
                suite=r.suite,
                passed=r.passed,
                failed=r.failed,
                outcome=r.outcome,
                tests=r.tests,
            )
            for r in repair.list_validation_runs(db, incident_id)
        ],
        model_usage=usage if isinstance(usage, dict) else None,
        review=ReviewView(
            id=review.id,
            decision=review.decision,
            reviewer=review.reviewer,
            patch_sha256=review.patch_sha256,
            comment=review.comment,
            created_at=review.created_at,
        )
        if review
        else None,
        limitations=_limitation(cause, any(e.to_state is State.VERIFIED for e in events)),
    )
