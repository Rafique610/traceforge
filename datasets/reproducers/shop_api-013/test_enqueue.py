"""Reproducer: placing an order must push its confirmation job to the local broker."""

import os
from decimal import Decimal

import pytest
from app.queue import OrderQueue, get_client
from app.settings import get_settings


@pytest.fixture(autouse=True)
def _fresh_env(monkeypatch):
    for key in [k for k in os.environ if k.startswith("REDIS_")]:
        monkeypatch.delenv(key)
    monkeypatch.setenv("REDIS_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_USER", "shopper")
    monkeypatch.setenv("DB_PASSWORD", "unused")
    get_settings.cache_clear()
    get_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_client.cache_clear()


def test_confirmation_job_reaches_the_broker(broker):
    commands = broker(6379)
    assert OrderQueue().enqueue_confirmation(7, Decimal("14.50"))
    pushes = [c for c in commands if c[0] == "LPUSH"]
    assert len(pushes) == 1 and pushes[0][1] == "orders:confirm"
