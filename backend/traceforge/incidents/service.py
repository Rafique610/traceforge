"""Lifecycle rules: guards and the single transition() entry point."""

import hashlib
import json
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from traceforge.evidence.redaction import redact_text
from traceforge.incidents import repository
from traceforge.incidents.models import AuditEvent, Incident
from traceforge.incidents.schemas import IncidentCreate
from traceforge.incidents.states import ALLOWED, State

ACTOR = re.compile(r"^(system|agent|reviewer:.+)$")


class IncidentNotFound(Exception):
    pass


class IllegalTransition(Exception):
    """Illegal move or failed guard. Mapped to HTTP 409 (see router.register_handlers)."""

    def __init__(self, current: State, requested: State, reason: str):
        super().__init__(f"{current} -> {requested}: {reason}")
        self.current = current


def _sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _guard_failure(
    db: Session, incident: Incident, to: State, payload: dict[str, Any]
) -> str | None:
    """Return why a guard fails, or None when it passes."""
    if to is State.DIAGNOSED:
        ids = payload.get("evidence_ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
            return "DIAGNOSED requires at least one evidence id in payload.evidence_ids"
        known = {e.id for e in repository.list_evidence(db, incident.id)}
        if not set(ids) <= known:
            return "payload.evidence_ids contains ids not stored for this incident"
    elif to is State.VERIFIED:
        if payload.get("repro_before") != "failed" or payload.get("repro_after") != "passed":
            return "VERIFIED requires repro_before == 'failed' and repro_after == 'passed'"
    elif to is State.REVIEWED:
        review_id = payload.get("review_id")
        if not isinstance(review_id, str) or not review_id:
            return "REVIEWED requires payload.review_id"
    return None


def _event(incident_id: uuid.UUID, actor: str, kind: str, frm, to, payload) -> AuditEvent:
    return AuditEvent(
        incident_id=incident_id,
        actor=actor,
        event_type=kind,
        from_state=frm,
        to_state=to,
        payload=payload,
        payload_sha256=_sha(payload),
    )


def create_incident(db: Session, data: IncidentCreate) -> Incident:
    incident = repository.add_incident(
        db,
        Incident(
            case_id=data.case_id,
            service=data.service,
            symptom=redact_text(data.symptom) if data.symptom else data.symptom,
            source=data.source or ("lab_case" if data.case_id else "manual"),
            state=State.CREATED,
        ),
    )
    repository.add_event(db, _event(incident.id, "system", "created", None, State.CREATED, {}))
    db.commit()
    return incident


def transition(
    db: Session,
    incident_id: uuid.UUID,
    to_state: State,
    actor: str,
    payload: dict[str, Any] | None = None,
) -> Incident:
    """Move an incident one step. Row lock + state change + audit row share one transaction."""
    payload = payload or {}
    if not ACTOR.match(actor):
        raise ValueError("actor must be system, agent or reviewer:<name>")
    incident = repository.get_incident(db, incident_id, lock=True)
    if incident is None:
        db.rollback()
        raise IncidentNotFound(str(incident_id))
    current = incident.state
    if to_state not in ALLOWED[current]:
        reason = "transition not allowed"
    else:
        reason = _guard_failure(db, incident, to_state, payload)
    if reason:
        db.rollback()  # releases the lock; nothing was written
        raise IllegalTransition(current, to_state, reason)
    incident.state = to_state
    repository.add_event(db, _event(incident.id, actor, "transition", current, to_state, payload))
    db.commit()
    return incident
