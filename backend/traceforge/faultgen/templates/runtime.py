# ruff: noqa: E501
"""runtime_dependency: no code or config change; the case's runtime setup stops a dependency.

Expected answer: diagnose the dependency, propose no patch. The tree is identical to the original, so the
reproducer demonstrates the symptom surface (a 503 when the broker cannot be reached) and passes on both
trees; the live check in the validator stops the real container and observes the real connection refusal.
"""

from traceforge.faultgen.model import CaseDraft
from traceforge.faultgen.templates.api_stub import api_conftest

CONFTEST_EXTRA = '''

@pytest.fixture
def real_queue_client(engine, monkeypatch):
    """Client wired to the real OrderQueue; the broker port has no listener (sandbox has no network)."""
    import os

    from app.queue import OrderQueue, get_client
    from app.settings import get_settings

    for key in [k for k in os.environ if k.startswith("REDIS_")]:
        monkeypatch.delenv(key)
    monkeypatch.setenv("REDIS_HOST", "127.0.0.1")
    monkeypatch.setenv("REDIS_PORT", "@@PORT@@")
    monkeypatch.setenv("DB_USER", "shopper")
    monkeypatch.setenv("DB_PASSWORD", "unused")
    get_settings.cache_clear()
    get_client.cache_clear()

    def _session():
        with Session(engine, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_queue] = lambda: OrderQueue()
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    get_client.cache_clear()
'''

REPRODUCER = '''"""Reproducer: order placement while the confirmation queue is unreachable."""

import pytest


def test_order_cannot_be_queued(real_queue_client, products):
    body = {"customer_email": "late@example.net", "items": [{"product_id": products[0].id, "quantity": 2}]}
    r = real_queue_client.post("/orders", json=body)
    assert r.status_code == 503
    assert "queue" in r.json()["detail"]
'''


def make(
    case_id: str,
    stop: tuple[str, ...] = ("lab_redis",),
    service: str = "shop_api",
    port: int = 6391,
) -> CaseDraft:
    conftest = api_conftest() + CONFTEST_EXTRA.replace("@@PORT@@", str(port))
    return CaseDraft(
        case_id=case_id,
        cause_class="runtime_dependency",
        fault_family="dependency_stopped",
        service=service,
        variant_group=f"runtime:{'+'.join(stop)}",
        log_format="uvicorn_access",
        distance=None,
        template="runtime.stop_dependency",
        params={"stop": list(stop)},
        reproducer_files={"conftest.py": conftest, "test_symptom.py": REPRODUCER},
        runtime={"stop": list(stop)},
        notes="diagnose only: no code or config change exists; reproducer passes on original and 'broken'",
    )
