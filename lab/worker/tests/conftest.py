"""Worker test fixtures. FakeRedis is a test-only in-memory stand-in for the few calls we use."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from worker.models import Base, Order
from worker.settings import WorkerSettings


class FakeRedis:
    def __init__(self):
        self.lists: dict[str, list[str]] = {}
        self.keys: dict[str, tuple[str, int | None]] = {}
        self.ping_failures = 0

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)

    def brpop(self, key, timeout=0):
        items = self.lists.get(key) or []
        return (key, items.pop()) if items else None

    def set(self, key, value, ex=None):
        self.keys[key] = (value, ex)

    def exists(self, key):
        return int(key in self.keys)

    def ping(self):
        if self.ping_failures > 0:
            self.ping_failures -= 1
            raise ConnectionError("not yet")
        return True


@pytest.fixture
def settings():
    return WorkerSettings(db_user="u", db_password="p", backoff_base_s=0.0)


@pytest.fixture
def redis_fake():
    return FakeRedis()


@pytest.fixture
def factory():
    eng = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(eng)
    f = sessionmaker(eng, expire_on_commit=False)
    with f() as s:
        s.add(Order(id=1, customer_email="a@b.co", status="pending"))
        s.commit()
    return f


@pytest.fixture
def job():
    def make(order_id=1, **extra):
        return json.dumps(
            {
                "job_id": "j1",
                "type": "order_confirmation",
                "order_id": order_id,
                "total": "14.50",
                "attempt": 0,
                **extra,
            }
        )

    return make
