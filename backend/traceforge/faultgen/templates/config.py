# ruff: noqa: E501
"""Configuration faults: a wrong default in a service's settings module.

Parameters: service (shop_api), field (redis_host | redis_port), bad_value. Everything else (gold key,
gold symbol span, tests) is derived. Distance is 1: the connection fails in app/queue.py, the cause is
read from app/settings.py.
"""

from traceforge.faultgen import lab_tree
from traceforge.faultgen.model import CaseDraft
from traceforge.faultgen.templates.broker_stub import BROKER_CONFTEST

SETTINGS = {"shop_api": ("lab/shop_api/app/settings.py", "Settings")}

FIELDS = {
    # field: (fault_family, python type, good default)
    "redis_host": ("wrong_host", "str", "localhost"),
    "redis_port": ("wrong_port", "int", "6379"),
}

_ENV = """    for key in [k for k in os.environ if k.startswith("REDIS_")]:
        monkeypatch.delenv(key)
"""

REPRODUCER = '''"""Reproducer: placing an order must push its confirmation job to the local broker."""

import os
from decimal import Decimal

import pytest
from app.queue import OrderQueue, get_client
from app.settings import get_settings


@pytest.fixture(autouse=True)
def _fresh_env(monkeypatch):
@@ENV@@    monkeypatch.setenv("DB_USER", "shopper")
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
'''

HIDDEN = """import json
import os
from decimal import Decimal

import pytest
import redis
from app.queue import OrderQueue, get_client
from app.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def _fresh_env(monkeypatch):
@@ENV@@    monkeypatch.setenv("DB_USER", "hidden_user")
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
    s = _settings(@@KW@@)
    client = redis.Redis(host=s.redis_host, port=s.redis_port, socket_connect_timeout=2, socket_timeout=2)
    OrderQueue(client=client).enqueue_confirmation(4242, Decimal("3.10"))
    last = commands[-1]
    assert last[:2] == ["LPUSH", s.order_queue]
    assert json.loads(last[2])["order_id"] == 4242


def test_queue_dependency_uses_the_environment(broker, monkeypatch):
    commands = broker(6379)
    monkeypatch.setenv("ORDER_QUEUE", "jobs:alt")
@@PIN@@    assert OrderQueue().ping() is True
    OrderQueue().enqueue_confirmation(9001, Decimal("0.99"))
    assert commands[-1][1] == "jobs:alt"


def test_documented_endpoint_is_the_default():
    s = _settings()
    assert (s.redis_host, s.redis_port) == ("localhost", 6379)
"""


def make(
    case_id: str,
    field: str = "redis_host",
    bad_value: str = "redis-broker.internal",
    service: str = "shop_api",
    log_format: str = "plain",
    lab=None,
) -> CaseDraft:
    lab = lab or lab_tree.repo_root() / "lab"
    path, cls = SETTINGS[service]
    family, typ, good = FIELDS[field]
    text = lab_tree.read_lf(lab.parent / path)
    good_lit = f'"{good}"' if typ == "str" else good
    bad_lit = f'"{bad_value}"' if typ == "str" else str(int(bad_value))
    old_line = f"    {field}: {typ} = {good_lit}\n"
    if text.count(old_line) != 1:
        raise ValueError(f"{path}: expected exactly one line {old_line!r}")
    new_text = text.replace(old_line, f"    {field}: {typ} = {bad_lit}\n")
    # hidden tests pin the *other* endpoint field so only the mutated one decides the outcome
    other_kw = "redis_port=6379" if field == "redis_host" else 'redis_host="127.0.0.1"'
    other_env = (
        'monkeypatch.setenv("REDIS_PORT", "6379")'
        if field == "redis_host"
        else 'monkeypatch.setenv("REDIS_HOST", "127.0.0.1")'
    )
    pin_vis = "" if field == "redis_host" else '    monkeypatch.setenv("REDIS_HOST", "127.0.0.1")\n'
    return CaseDraft(
        case_id=case_id,
        cause_class="configuration",
        fault_family=family,
        service=service,
        variant_group=f"settings_default:{service}:{field}",
        log_format=log_format,
        distance=1,
        template="config.settings_default",
        params={"field": field, "bad_value": bad_value},
        edits={path: new_text},
        gold_config_keys=[f"{service}.{field.upper()}"],
        gold_symbols=[(path, f"{cls}.{field}")],
        reproducer_files={
            "conftest.py": BROKER_CONFTEST,
            "test_enqueue.py": REPRODUCER.replace("@@ENV@@", _ENV + pin_vis),
        },
        hidden_files={
            "conftest.py": BROKER_CONFTEST,
            "test_hidden_broker.py": HIDDEN.replace("@@ENV@@", _ENV)
            .replace("@@KW@@", other_kw)
            .replace("@@PIN@@", f"    {other_env}\n"),
        },
        notes=(
            "distance is a manual estimate: connection fails in app/queue.py, value comes from "
            "app/settings.py"
            + (
                "; the lab's own default-value test also fails for redis_port"
                if field == "redis_port"
                else ""
            )
        ),
    )
