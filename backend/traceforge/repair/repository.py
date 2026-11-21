"""Patches and validation runs: add and read only."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from traceforge.repair.models import Patch, ValidationRun


def add_patch(db: Session, patch: Patch) -> Patch:
    db.add(patch)
    db.flush()
    return patch


def get_patch(db: Session, incident_id: uuid.UUID) -> Patch | None:
    return db.scalars(select(Patch).where(Patch.incident_id == incident_id)).one_or_none()


def add_validation_run(db: Session, run: ValidationRun) -> ValidationRun:
    db.add(run)
    db.flush()
    return run


def list_validation_runs(db: Session, incident_id: uuid.UUID) -> list[ValidationRun]:
    stmt = select(ValidationRun).where(ValidationRun.incident_id == incident_id)
    return list(db.scalars(stmt.order_by(ValidationRun.id)))
