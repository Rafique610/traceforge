"""Config loading: env -> Settings (no Docker, no files)."""

import pytest
from app.settings import Settings
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in (
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "DB_POOL_SIZE",
        "REDIS_HOST",
        "REDIS_PORT",
        "ORDER_QUEUE",
    ):
        monkeypatch.delenv(k, raising=False)


def test_loads_from_env(monkeypatch):
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_HOST", "lab_db")
    monkeypatch.setenv("REDIS_HOST", "lab_redis")
    monkeypatch.setenv("REDIS_PORT", "6380")
    monkeypatch.setenv("ORDER_QUEUE", "q1")
    s = Settings()
    assert (s.db_host, s.redis_host, s.redis_port, s.order_queue) == (
        "lab_db",
        "lab_redis",
        6380,
        "q1",
    )
    assert (
        s.database_url.render_as_string(hide_password=True)
        == "postgresql+psycopg://u:***@lab_db:5432/shop"
    )


def test_defaults(monkeypatch):
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    s = Settings()
    assert (s.db_port, s.db_pool_size, s.redis_port, s.order_queue) == (
        5432,
        5,
        6379,
        "orders:confirm",
    )


def test_credentials_are_required():
    with pytest.raises(ValidationError):
        Settings()


def test_password_is_not_in_repr(monkeypatch):
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "s3cret-value")
    assert "s3cret-value" not in repr(Settings())


def test_bad_port_rejected(monkeypatch):
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_PORT", "not-a-port")
    with pytest.raises(ValidationError):
        Settings()
