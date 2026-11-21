"""Postgres-only checks: row locking, JSONB payload round trip. Skipped when Postgres is down."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from traceforge.database import engine
from traceforge.incidents import service
from traceforge.incidents.models import AuditEvent, Incident
from traceforge.incidents.schemas import IncidentCreate
from traceforge.incidents.service import IllegalTransition
from traceforge.incidents.states import State


def _reachable() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM incidents LIMIT 1"))
        return True
    except OperationalError:
        return False
    except Exception:  # table missing: migration not applied
        return False


pytestmark = pytest.mark.skipif(not _reachable(), reason="Postgres + migration needed")
Session = sessionmaker(bind=engine, expire_on_commit=False)


def test_concurrent_transitions_only_one_wins_and_audit_is_exact():
    with Session() as db:
        incident = service.create_incident(db, IncidentCreate(symptom="boom", service="shop_api"))
    iid = incident.id

    def attempt(_: int) -> str:
        with Session() as db:
            try:
                service.transition(db, iid, State.SNAPSHOT_LOCKED, "system", {"n": {"k": [1, 2]}})
                return "ok"
            except IllegalTransition:
                return "illegal"

    try:
        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(attempt, range(8)))
        assert results.count("ok") == 1
        with Session() as db:
            events = db.scalars(select(AuditEvent).where(AuditEvent.incident_id == iid)).all()
            assert [e.event_type for e in events].count("transition") == 1
            moved = next(e for e in events if e.event_type == "transition")
            assert moved.payload == {"n": {"k": [1, 2]}}  # JSONB round trip
            assert db.get(Incident, iid).state == State.SNAPSHOT_LOCKED
    finally:
        with Session() as db:  # clean up test rows (ORM only)
            for e in db.scalars(select(AuditEvent).where(AuditEvent.incident_id == iid)):
                db.delete(e)
            db.delete(db.get(Incident, iid))
            db.commit()
