import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from traceforge.database import Base
from traceforge.incidents.states import State

Json = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(UTC)


def _state_enum(name: str) -> Enum:
    # VARCHAR + CHECK instead of a native PG enum: adding a state later needs no ALTER TYPE.
    return Enum(State, native_enum=False, length=32, create_constraint=True, name=name)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[str | None] = mapped_column(String(128))
    service: Mapped[str | None] = mapped_column(String(128))
    symptom: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))  # lab_case / manual / github
    state: Mapped[State] = mapped_column(
        _state_enum("ck_incidents_state"), index=True, default=State.CREATED
    )
    cause_class: Mapped[str | None] = mapped_column(String(64))
    base_sha: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class EvidenceItemRow(Base):
    __tablename__ = "evidence_items"

    # EV-xxxx ids are only unique within one bundle, so the key includes the incident.
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), primary_key=True)
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    service: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    path: Mapped[str | None] = mapped_column(String(512))
    line: Mapped[int | None] = mapped_column(Integer)
    ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    """Insert-only. The repository exposes no update or delete."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    actor: Mapped[str] = mapped_column(String(128))  # system / agent / reviewer:<name>
    event_type: Mapped[str] = mapped_column(String(64))
    from_state: Mapped[State | None] = mapped_column(_state_enum("ck_audit_events_from_state"))
    to_state: Mapped[State | None] = mapped_column(_state_enum("ck_audit_events_to_state"))
    payload: Mapped[dict] = mapped_column(Json, default=dict)
    payload_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
