# ruff: noqa: E501
"""Source text of the shared conftest for API-level reproducer/hidden tests.

Self-contained on purpose: reproducer and hidden dirs are mounted alone in the sandbox, so they
cannot reuse the lab's own tests/conftest.py. In-memory SQLite and a recording queue are labelled
test doubles (no Docker, no network).
"""

API_CONFTEST = '''"""Test plumbing: in-memory SQLite and a recording queue (test doubles)."""

from decimal import Decimal

import pytest
from app.db import get_session
from app.main import app
from app.models import Base, Product
from app.queue import get_queue
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


class RecordingQueue:
    def __init__(self):
        self.jobs = []
        self.alive = True

    def enqueue_confirmation(self, order_id, total):
        self.jobs.append((order_id, total))
        return "job"

    def ping(self):
        return True

    def worker_alive(self):
        return self.alive


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine, expire_on_commit=False) as s:
        yield s


@pytest.fixture
def products(session):
    rows = [Product(name="@@P1@@", price=Decimal("@@P1PRICE@@")), Product(name="@@P2@@", price=Decimal("@@P2PRICE@@"))]
    session.add_all(rows)
    session.commit()
    return rows


@pytest.fixture
def queue():
    return RecordingQueue()


@pytest.fixture
def client(engine, queue):
    def _session():
        with Session(engine, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_queue] = lambda: queue
    yield TestClient(app)
    app.dependency_overrides.clear()
'''


def api_conftest(p1=("Cup", "4.10"), p2=("Tin", "9.90")) -> str:
    """Products differ between visible and hidden suites so their inputs differ (D31)."""
    return (
        API_CONFTEST.replace("@@P1@@", p1[0])
        .replace("@@P1PRICE@@", p1[1])
        .replace("@@P2@@", p2[0])
        .replace("@@P2PRICE@@", p2[1])
    )
