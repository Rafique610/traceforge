"""Frozen patches and validation runs. Insert-only: ORM update/delete is refused."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from traceforge.database import Base

Json = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(UTC)


def forbid_mutation(*models: type) -> None:
    def _refuse(*_args) -> None:
        raise RuntimeError("insert-only table: rows are never updated or deleted")

    for m in models:
        event.listen(m, "before_update", _refuse)
        event.listen(m, "before_delete", _refuse)


class Patch(Base):
    """The frozen patch of an incident. sha256 = SHA-256 of the UTF-8 diff text."""

    __tablename__ = "patches"
    __table_args__ = (UniqueConstraint("incident_id", name="uq_patches_incident_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    diff: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    paths: Mapped[list] = mapped_column(Json, default=list)
    signature_changed: Mapped[bool] = mapped_column(Boolean, default=False)
    impact: Mapped[list] = mapped_column(Json, default=list)  # [{"symbol": str, "impacted": [..]}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ValidationRun(Base):
    __tablename__ = "validation_runs"
    __table_args__ = (
        CheckConstraint("suite in ('reproducer','visible','hidden')", name="ck_validation_suite"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    attempt: Mapped[int] = mapped_column(Integer)  # 0 = unpatched baseline
    suite: Mapped[str] = mapped_column(String(16))
    passed: Mapped[int] = mapped_column(Integer)
    failed: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(32))
    tests: Mapped[list] = mapped_column(Json, default=list)  # [{"id": str, "outcome": str}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


forbid_mutation(Patch, ValidationRun)
