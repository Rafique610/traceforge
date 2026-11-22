# ruff: noqa: E501
"""runtime_dependency and insufficient_evidence variants beyond the two seed templates.

runtime_dependency: no code or config change; a dependency is stopped. The reproducer shows the symptom
surface against a closed port (sandbox has no network) and passes on both trees; the validator's live
check stops the real container (lab_redis or lab_db) and observes the real failure.
insufficient_evidence: an intermittent symptom with logs withheld; the right answer is to abstain.
Variants of one group differ only in ports and order details, and always share a split.
"""

from traceforge.faultgen.model import CaseDraft
from traceforge.faultgen.templates.api_stub import api_conftest

REAL_DEPS = '''

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
    monkeypatch.setenv("REDIS_PORT", "@@RPORT@@")
    monkeypatch.setenv("DB_USER", "shopper")
    monkeypatch.setenv("DB_PASSWORD", "unused")
    get_settings.cache_clear()
    get_client.cache_clear()
    db = _ce(f"postgresql+psycopg://shopper:unused@127.0.0.1:@@DPORT@@/shop", connect_args={"connect_timeout": 2}) if @@REAL_DB@@ else engine

    def _session():
        with Session(db, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_queue] = (lambda: OrderQueue()) if @@REAL_Q@@ else (lambda: _Up())
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
'''

RUNTIME = {
    "lab_redis:health": dict(
        stop="lab_redis",
        real_db=False,
        real_q=True,
        test='''"""Reproducer: the health endpoint while the job broker is unreachable."""


def test_health_reports_the_broker(real_deps_client):
    r = real_deps_client.get("/health")
    assert r.status_code == 503
    assert r.json()["redis"].startswith("down")
    assert r.json()["db"] == "ok"
''',
    ),
    "lab_db:health": dict(
        stop="lab_db",
        real_db=True,
        real_q=False,
        test='''"""Reproducer: the health endpoint while the database is unreachable."""


def test_health_reports_the_database(real_deps_client):
    r = real_deps_client.get("/health")
    assert r.status_code == 503
    assert r.json()["db"].startswith("down")
    assert r.json()["redis"] == "ok"
''',
    ),
    "lab_db:catalogue": dict(
        stop="lab_db",
        real_db=True,
        real_q=False,
        test='''"""Reproducer: browsing the catalogue while the database is unreachable."""


def test_catalogue_is_unavailable(real_deps_client):
    assert real_deps_client.get("/products").status_code == 500
    assert real_deps_client.get("/health/live").status_code == 200
''',
    ),
}
RUNTIME_PORTS = [(6391, 5491), (6392, 5492), (6393, 5493), (6394, 5494)]


def make_runtime(case_id: str, group: str, variant: int) -> CaseDraft:
    g = RUNTIME[group]
    rport, dport = RUNTIME_PORTS[variant]
    conftest = api_conftest() + (
        REAL_DEPS.replace("@@RPORT@@", str(rport)).replace("@@DPORT@@", str(dport))
        .replace("@@REAL_DB@@", str(g["real_db"])).replace("@@REAL_Q@@", str(g["real_q"]))
    )  # fmt: skip
    return CaseDraft(
        case_id=case_id, cause_class="runtime_dependency", fault_family="dependency_stopped", service="shop_api",
        variant_group=f"runtime:{group}", log_format="uvicorn_access", distance=None,
        template="outages.runtime", params={"group": group, "ports": [rport, dport]},
        reproducer_files={"conftest.py": conftest, "test_symptom.py": g["test"]},
        runtime={"stop": [g["stop"]]},
        notes="diagnose only: no code or config change exists; reproducer passes on original and 'broken'",
    )  # fmt: skip


FLAKY_QUEUE = '''

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
    q = FlakyQueue(@@N@@)

    def _session():
        with Session(engine, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_queue] = lambda: q
    yield TestClient(app)
    app.dependency_overrides.clear()
'''

INSUFFICIENT = {
    "sporadic_order_503": dict(
        extra=FLAKY_QUEUE,
        test='''"""Reproducer: some orders are refused with 503 and the same order succeeds when retried."""


def test_retry_of_a_refused_order_succeeds(flaky_client, products):
    body = {"customer_email": "@@EMAIL@@", "items": [{"product_id": products[0].id, "quantity": 1}]}
    codes = [flaky_client.post("/orders", json=body).status_code for _ in range(@@TRIES@@)]
    assert 503 in codes and codes[-1] == 201
''',
    ),
    "health_flaps": dict(
        extra="",
        test='''"""Reproducer: the health endpoint alternates between healthy and degraded."""


def test_health_alternates(client, queue):
    seen = []
    for alive in @@PATTERN@@:
        queue.alive = alive
        seen.append(client.get("/health").status_code)
    assert seen == @@CODES@@
''',
    ),
    "unconfirmed_orders": dict(
        extra="",
        test='''"""Reproducer: orders are accepted and queued, yet customers say some confirmations never arrive."""


def test_orders_are_accepted_and_queued(client, products, queue):
    for email in ("@@EMAIL@@", "second.@@EMAIL@@"):
        body = {"customer_email": email, "items": [{"product_id": products[1].id, "quantity": 2}]}
        assert client.post("/orders", json=body).status_code == 201
    assert len(queue.jobs) == 2
''',
    ),
}
PATTERNS = [(True, False), (True, False, True, False), (False, True, False), (True, True, False)]
INSUFFICIENT_VARIANTS = [
    ("ana@example.org", 1, 3),
    ("bo@example.net", 2, 4),
    ("cy@example.com", 1, 2),
    ("di@example.io", 3, 5),
]


def make_insufficient(case_id: str, group: str, variant: int) -> CaseDraft:
    g = INSUFFICIENT[group]
    email, n, tries = INSUFFICIENT_VARIANTS[variant]
    conftest = api_conftest() + g["extra"].replace("@@N@@", str(n))
    pat = PATTERNS[variant]
    test = (g["test"].replace("@@EMAIL@@", email).replace("@@TRIES@@", str(tries))
            .replace("@@PATTERN@@", repr(pat)).replace("@@CODES@@", repr([200 if a else 503 for a in pat])))  # fmt: skip
    return CaseDraft(
        case_id=case_id, cause_class="insufficient_evidence", fault_family="intermittent_no_logs", service="shop_api",
        variant_group=f"insufficient:{group}", log_format="none", distance=None,
        template="outages.insufficient", params={"group": group, "variant": variant},
        reproducer_files={"conftest.py": conftest, "test_symptom.py": test},
        runtime={"logs": "suppressed", "symptom": "intermittent"},
        notes="no cause is determinable: logs withheld and the contract is silent on the intermittent symptom",
    )  # fmt: skip
