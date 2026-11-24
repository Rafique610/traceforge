"""All DB access for incidents. Audit events: add only (no update/delete method exists)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from traceforge.contracts.evidence import EvidenceBundle
from traceforge.incidents.models import AuditEvent, EvidenceItemRow, Incident
from traceforge.incidents.states import State


def add_incident(db: Session, incident: Incident) -> Incident:
    db.add(incident)
    db.flush()
    return incident


def get_incident(db: Session, incident_id: uuid.UUID, *, lock: bool = False) -> Incident | None:
    # with_for_update -> SELECT ... FOR UPDATE on Postgres (ignored by SQLite).
    stmt = select(Incident).where(Incident.id == incident_id)
    return db.scalars(stmt.with_for_update() if lock else stmt).one_or_none()


def list_incidents(
    db: Session, state: State | None, limit: int, offset: int
) -> tuple[list[Incident], int]:
    where = [Incident.state == state] if state else []
    total = db.scalar(select(func.count()).select_from(Incident).where(*where)) or 0
    stmt = select(Incident).where(*where).order_by(Incident.created_at.desc(), Incident.id)
    return list(db.scalars(stmt.limit(limit).offset(offset))), total


def add_event(db: Session, event: AuditEvent) -> AuditEvent:
    db.add(event)
    db.flush()
    return event


def list_events(db: Session, incident_id: uuid.UUID) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(AuditEvent.incident_id == incident_id)
    return list(db.scalars(stmt.order_by(AuditEvent.id)))


def list_evidence(db: Session, incident_id: uuid.UUID) -> list[EvidenceItemRow]:
    stmt = select(EvidenceItemRow).where(EvidenceItemRow.incident_id == incident_id)
    return list(db.scalars(stmt.order_by(EvidenceItemRow.id)))


def save_evidence_bundle(db: Session, bundle: EvidenceBundle) -> None:
    """Persist a bundle's items for its incident (caller commits). Re-saving an id is an error."""
    incident_id = uuid.UUID(bundle.incident_id)
    db.add_all(
        EvidenceItemRow(
            incident_id=incident_id, **item.model_dump(exclude={"scope", "basis", "origin"})
        )
        for item in bundle.items
    )
    db.flush()
