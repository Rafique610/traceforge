"""Test plumbing: in-memory SQLite and a recording queue (test doubles)."""

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
    rows = [Product(name="Cup", price=Decimal("4.10")), Product(name="Tin", price=Decimal("9.90"))]
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


class FlakyQueue(RecordingQueue):
    """Fails the first `n` enqueues, then works (stand-in for an unexplained transient fault)."""

    def __init__(self, n):
        super().__init__()
        self.left = n

    def enqueue_confirmation(self, order_id, total):
        if self.left:
            self.left -= 1
            raise ConnectionError("transient")
        return super().enqueue_confirmation(order_id, total)


@pytest.fixture
def flaky_client(engine):
    q = FlakyQueue(3)

    def _session():
        with Session(engine, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_queue] = lambda: q
    yield TestClient(app)
    app.dependency_overrides.clear()
