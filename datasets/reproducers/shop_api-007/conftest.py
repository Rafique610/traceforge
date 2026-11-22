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


@pytest.fixture
def real_deps_client(engine, monkeypatch):
    """Real OrderQueue and/or a real Postgres engine pointed at ports with no listener."""
    import os

    from app.queue import OrderQueue, get_client
    from app.settings import get_settings
    from sqlalchemy import create_engine as _ce

    for key in [k for k in os.environ if k.startswith(("REDIS_", "DB_"))]:
        monkeypatch.delenv(key)
    monkeypatch.setenv("REDIS_HOST", "127.0.0.1")
    monkeypatch.setenv("REDIS_PORT", "6394")
    monkeypatch.setenv("DB_USER", "shopper")
    monkeypatch.setenv("DB_PASSWORD", "unused")
    get_settings.cache_clear()
    get_client.cache_clear()
    db = _ce(f"postgresql+psycopg://shopper:unused@127.0.0.1:5494/shop", connect_args={"connect_timeout": 2}) if False else engine

    def _session():
        with Session(db, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_queue] = (lambda: OrderQueue()) if True else (lambda: _Up())
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    get_client.cache_clear()


class _Up:
    def enqueue_confirmation(self, order_id, total):
        return "job"

    def ping(self):
        return True

    def worker_alive(self):
        return True
