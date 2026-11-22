import json
import os
from decimal import Decimal

import pytest
import redis
from app.queue import OrderQueue, get_client
from app.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def _fresh_env(monkeypatch):
    for key in [k for k in os.environ if k.startswith("REDIS_")]:
        monkeypatch.delenv(key)
    monkeypatch.setenv("DB_USER", "hidden_user")
    monkeypatch.setenv("DB_PASSWORD", "hidden_pw")
    get_settings.cache_clear()
    get_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_client.cache_clear()


def _settings(**kw):
    return Settings(db_user="hidden_user", db_password="hidden_pw", **kw)


def test_client_built_from_settings_delivers_a_job(broker):
    commands = broker(6379)
    s = _settings(redis_host="127.0.0.1")
    client = redis.Redis(host=s.redis_host, port=s.redis_port, socket_connect_timeout=2, socket_timeout=2)
    OrderQueue(client=client).enqueue_confirmation(4242, Decimal("3.10"))
    last = commands[-1]
    assert last[:2] == ["LPUSH", s.order_queue]
    assert json.loads(last[2])["order_id"] == 4242


def test_queue_dependency_uses_the_environment(broker, monkeypatch):
    commands = broker(6379)
    monkeypatch.setenv("ORDER_QUEUE", "jobs:alt")
    monkeypatch.setenv("REDIS_HOST", "127.0.0.1")
    assert OrderQueue().ping() is True
    OrderQueue().enqueue_confirmation(9001, Decimal("0.99"))
    assert commands[-1][1] == "jobs:alt"


def test_documented_endpoint_is_the_default():
    s = _settings()
    assert (s.redis_host, s.redis_port) == ("localhost", 6379)
