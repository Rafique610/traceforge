"""Collector unit tests. The Docker client here is a FAKE used only to isolate the unit tests;
real-lab verification lives in test_evidence_live.py."""

from pathlib import Path

import pytest

from traceforge.contracts.evidence import EvidenceBundle
from traceforge.evidence import EvidenceCollector, EvidenceConfig
from traceforge.evidence import compose as compose_mod
from traceforge.evidence import config as config_mod
from traceforge.evidence.pathmap import to_repo_path

FIX = Path(__file__).parent / "fixtures"
CFG = EvidenceConfig(probes={})
PW = "Tr0ub4dor-lab-pw"


class FakeContainer:
    def __init__(self, service, status="running", health="healthy", env=None, log=""):
        self.name = f"traceforge-lab-{service}-1"
        self._log = log
        self.attrs = {
            "State": {
                "Status": status,
                "Health": {"Status": health},
                "ExitCode": 1,
                "StartedAt": "t",
            },
            "RestartCount": 0,
            "Config": {"Env": env or [], "Image": "img"},
        }

    def logs(self, **kw):
        assert kw["tail"] > 0 and kw["since"] > 0  # always bounded
        return self._log.encode()


class FakeClient:
    def __init__(self, by_service):
        self.by_service = by_service
        self.containers = self

    def list(self, all=True, filters=None):
        svc = next(x.split("=", 1)[1] for x in filters["label"] if "service=" in x)
        return [self.by_service[svc]] if svc in self.by_service else []


def _client(**over):
    env = ["REDIS_HOST=lab_redis_typo", "REDIS_PORT=6379", f"DB_PASSWORD={PW}", "PATH=/usr/bin"]
    log = (FIX / "worker_bad_redis.log").read_text("utf-8") + f"\nconnect failed password={PW}\n"
    base = {
        "lab_db": FakeContainer("lab_db"),
        "lab_redis": FakeContainer("lab_redis"),
        "shop_api": FakeContainer("shop_api"),
        "worker": FakeContainer("worker", "exited", "unhealthy", env, log),
    }
    base.update(over)
    return FakeClient(base)


def test_bundle_valid_stable_and_redacted():
    col = EvidenceCollector(CFG, _client()).collect_detailed("inc-1", "worker", None)
    b = col.bundle
    EvidenceBundle.model_validate(b.model_dump())
    ids = [i.id for i in b.items]
    assert ids == [f"EV-{n:04d}" for n in range(1, len(ids) + 1)]
    kinds = {i.kind for i in b.items}
    assert {"health", "log", "trace_frame", "config", "compose"} <= kinds
    assert col.log_format == "plain"
    blob = "\n".join(i.content for i in b.items)
    assert PW not in blob and "«redacted:" in blob
    assert "PATH=" not in blob  # not allowlisted
    assert "REDIS_HOST=lab_redis_typo" in blob  # allowlisted, non-secret
    for i in b.items:
        import hashlib

        assert i.sha256 == hashlib.sha256(i.content.encode()).hexdigest()
        assert i.path is None or ("\\" not in i.path and ":" not in i.path)
    again = EvidenceCollector(CFG, _client()).collect("inc-1", "worker", None)
    assert [(i.id, i.sha256) for i in again.items] == [(i.id, i.sha256) for i in b.items]


def test_trace_frames_mapped_to_repo_paths_and_external_marked():
    b = EvidenceCollector(CFG, _client()).collect("inc-1", "worker", None)
    frames = [i for i in b.items if i.kind == "trace_frame"]
    mapped = {(i.path, i.line) for i in frames if i.path}
    assert ("lab/worker/queue.py", 36) in mapped and ("lab/worker/main.py", 28) in mapped
    ext = [i for i in frames if i.content.startswith("[external]")]
    assert ext and all(i.path is None for i in ext)
    assert not any("site-packages" in (i.path or "") for i in frames)


def test_absent_container_is_health_evidence_and_no_logs():
    client = _client()
    del client.by_service["lab_redis"]
    b = EvidenceCollector(CFG, client).collect("inc-1", "worker", None)
    assert any(i.kind == "health" and "lab_redis: absent" in i.content for i in b.items)


def test_empty_logs_yield_no_log_items():
    client = _client(worker=FakeContainer("worker", log=""))
    col = EvidenceCollector(CFG, client).collect_detailed("inc-1", "worker", None)
    assert not [i for i in col.bundle.items if i.kind == "log"]
    assert col.log_format == "none"


def test_unknown_service_rejected():
    with pytest.raises(ValueError):
        EvidenceCollector(CFG, _client()).collect("i", "nope", None)


def test_compose_parse_and_sha():
    text, sha = compose_mod.read_compose(CFG)
    assert len(sha) == 64
    svcs = {s.name: s for s in compose_mod.service_items(text, CFG)}
    assert set(svcs) == {"lab_db", "lab_redis", "shop_api", "worker"}
    assert "depends_on: ['lab_db', 'lab_redis', 'shop_api']" in svcs["worker"].content
    assert "REDIS_HOST=lab_redis" in svcs["worker"].content
    assert "DB_PASSWORD=«redacted:password»" in svcs["worker"].content
    assert text.splitlines()[svcs["worker"].line - 1].strip() == "worker:"


def test_declared_settings_static():
    src = (
        "class Settings(BaseSettings):\n"
        "    redis_host: str = 'x'\n"
        "    db_password: SecretStr = 'p'\n"
    )
    assert config_mod.declared_settings(src) == [
        ("redis_host", "[str] = 'x'", 2),
        ("db_password", "[SecretStr] = <redacted>", 3),
    ]
    assert config_mod.declared_settings("def (:") == []


def test_path_mapping():
    assert to_repo_path("/app/app/orders.py", "shop_api", CFG) == "lab/shop_api/app/orders.py"
    assert to_repo_path("/app/worker/queue.py", "worker", CFG) == "lab/worker/queue.py"
    assert to_repo_path("/app/lab/shop_api/app/orders.py", "shop_api", CFG) == (
        "lab/shop_api/app/orders.py"
    )
    assert to_repo_path("/app/app/does_not_exist.py", "shop_api", CFG) is None
    assert to_repo_path("/opt/venv/lib/python3.12/site-packages/x.py", "shop_api", CFG) is None
    assert to_repo_path("/app/app/../../../etc/passwd", "shop_api", CFG) is None
