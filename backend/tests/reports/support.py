"""Shared fixtures for report and review tests (SQLite stand-in; no row locking)."""

import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from traceforge.contracts.evidence import EvidenceBundle  # noqa: F401
from traceforge.database import Base, get_db
from traceforge.incidents import models as _m  # noqa: F401
from traceforge.incidents import service
from traceforge.incidents.models import EvidenceItemRow, Incident
from traceforge.incidents.router import register_handlers as register_incident_handlers
from traceforge.incidents.schemas import IncidentCreate
from traceforge.incidents.states import State
from traceforge.repair import models as _r  # noqa: F401
from traceforge.repair import repository as repair
from traceforge.repair.models import Patch, ValidationRun
from traceforge.reports.router import router as report_router
from traceforge.reviews import models as _rv  # noqa: F401
from traceforge.reviews.router import register_handlers as register_review_handlers
from traceforge.reviews.router import router as review_router

DIFF = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
SHA = hashlib.sha256(DIFF.encode()).hexdigest()


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def client(session_factory):
    def override():
        with session_factory() as session:
            yield session

    app = FastAPI()  # own app: routers are registered in main.py by the orchestrator
    app.include_router(review_router)
    app.include_router(report_router)
    register_incident_handlers(app)
    register_review_handlers(app)
    app.dependency_overrides[get_db] = override
    return TestClient(app)


def make_incident(db, *, cause: str, path: list[State], payloads: dict | None = None) -> Incident:
    """Create an incident and walk it through `path` with the given transition payloads."""
    inc = service.create_incident(db, IncidentCreate(case_id="case-1"))
    inc.cause_class, inc.base_sha = cause, "abc123"
    db.add(
        EvidenceItemRow(
            incident_id=inc.id,
            id="EV-0001",
            kind="log",
            service="shop_api",
            content="boom",
            sha256="0" * 64,
            path="app.py",
            line=3,
        )
    )
    db.commit()
    payloads = payloads or {}
    for s in path:
        service.transition(db, inc.id, s, "system", payloads.get(s, {}))
    return inc


PRE = [State.SNAPSHOT_LOCKED, State.EVIDENCE_COLLECTED, State.CONTEXT_RETRIEVED]
DIAG = {State.DIAGNOSED: {"evidence_ids": ["EV-0001"], "target": "app.py::f"}}


def verified_incident(db):
    path = [
        *PRE,
        State.DIAGNOSED,
        State.PATCH_PROPOSED,
        State.VALIDATING,
        State.VERIFIED,
        State.REVIEW_PENDING,
    ]
    payloads = {**DIAG, State.VERIFIED: {"repro_before": "failed", "repro_after": "passed"}}
    inc = make_incident(db, cause="application_code", path=path, payloads=payloads)
    repair.add_patch(
        db,
        Patch(
            incident_id=inc.id,
            diff=DIFF,
            sha256=SHA,
            paths=["app.py"],
            signature_changed=True,
            impact=[{"symbol": "app.py::f", "impacted": ["app.py::g"]}],
        ),
    )
    for attempt, suite, p, f in [(0, "reproducer", 0, 1), (1, "reproducer", 1, 0)]:
        repair.add_validation_run(
            db,
            ValidationRun(
                incident_id=inc.id,
                attempt=attempt,
                suite=suite,
                passed=p,
                failed=f,
                outcome="passed" if f == 0 else "failed",
                tests=[{"id": "t::a", "outcome": "x"}],
            ),
        )
    db.commit()
    return inc


def runtime_incident(db):
    path = [*PRE, State.DIAGNOSED, State.REVIEW_PENDING]
    payloads = {State.DIAGNOSED: {"evidence_ids": ["EV-0001"], "target": "redis"}}
    return make_incident(db, cause="runtime_dependency", path=path, payloads=payloads)


def insufficient_incident(db):
    path = [*PRE, State.INCONCLUSIVE, State.REVIEW_PENDING]
    payloads = {State.INCONCLUSIVE: {"missing_evidence": ["worker logs", "db metrics"]}}
    return make_incident(db, cause="insufficient_evidence", path=path, payloads=payloads)


def unverified_incident(db):
    path = [
        *PRE,
        State.DIAGNOSED,
        State.PATCH_PROPOSED,
        State.VALIDATING,
        State.UNVERIFIED,
        State.REVIEW_PENDING,
    ]
    inc = make_incident(db, cause="configuration", path=path, payloads=DIAG)
    repair.add_patch(db, Patch(incident_id=inc.id, diff=DIFF, sha256=SHA, paths=["app.py"]))
    db.commit()
    return inc
