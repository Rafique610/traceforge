"""Unit-test fixtures: in-memory SQLite and a recording stand-in queue (test-only fake)."""

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


class FakeQueue:
    """Test double for OrderQueue; records jobs instead of talking to Redis."""

    def __init__(self):
        self.jobs: list[tuple[int, Decimal]] = []
        self.fail = False

    def enqueue_confirmation(self, order_id, total):
        if self.fail:
            raise ConnectionError("redis down")
        self.jobs.append((order_id, total))
        return "job-1"

    def ping(self):
        if self.fail:
            raise ConnectionError("redis down")
        return True

    def worker_alive(self):
        return True


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine, expire_on_commit=False) as s:
        yield s


@pytest.fixture
def products(session):
    rows = [
        Product(name="Mug", price=Decimal("7.25")),
        Product(name="Beans", price=Decimal("18.50")),
    ]
    session.add_all(rows)
    session.commit()
    return rows


@pytest.fixture
def queue():
    return FakeQueue()


@pytest.fixture
def client(engine, queue):
    def _session():
        with Session(engine, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_queue] = lambda: queue
    yield TestClient(
        app
    )  # no `with`: skip lifespan (it would create tables on the real engine)
    app.dependency_overrides.clear()
