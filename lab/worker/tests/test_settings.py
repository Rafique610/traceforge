"""Worker config loading (no Docker)."""

import pytest
from pydantic import ValidationError
from worker.settings import WorkerSettings

KEYS = (
    "REDIS_HOST",
    "REDIS_PORT",
    "ORDER_QUEUE",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("REDIS_HOST", "lab_redis")
    monkeypatch.setenv("ORDER_QUEUE", "q9")
    s = WorkerSettings()
    assert (s.redis_host, s.redis_port, s.order_queue, s.dead_queue) == (
        "lab_redis",
        6379,
        "q9",
        "q9:dead",
    )


def test_credentials_required():
    with pytest.raises(ValidationError):
        WorkerSettings()


def test_defaults_match_the_api_contract(monkeypatch):
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    s = WorkerSettings()
    assert s.order_queue == "orders:confirm" and s.max_retries == 3
