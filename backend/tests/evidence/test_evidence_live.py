"""Live checks against the read-only Docker socket proxy (and the lab when it is up).

Start the proxy: docker compose -f backend/traceforge/evidence/docker-proxy.compose.yaml up -d
Skipped automatically when the proxy is not reachable.
"""

import urllib.error
import urllib.request

import docker
import pytest
from docker.errors import APIError, DockerException

from traceforge.contracts.evidence import EvidenceBundle
from traceforge.evidence import EvidenceCollector, EvidenceConfig

pytestmark = pytest.mark.docker
BASE = "http://127.0.0.1:2375"


def _call(method: str, path: str, body: bytes | None = None) -> int:
    req = urllib.request.Request(BASE + path, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


@pytest.fixture(scope="module", autouse=True)
def proxy_up():
    try:
        urllib.request.urlopen(BASE + "/_ping", timeout=3)
    except OSError:
        pytest.skip("docker socket proxy not running on 127.0.0.1:2375")


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/containers/create"),
        ("POST", "/v1.43/containers/create?name=evil"),
        ("POST", "/containers/anything/stop"),
        ("POST", "/containers/anything/kill"),
        ("POST", "/containers/anything/exec"),
        ("POST", "/containers/anything/start"),
        ("POST", "/containers/anything/restart"),
        ("DELETE", "/containers/anything"),
        ("PUT", "/containers/anything/archive?path=/"),
        ("POST", "/exec/anything/start"),
        ("POST", "/images/create?fromImage=alpine"),
        ("POST", "/build"),
        ("POST", "/networks/create"),
        ("POST", "/volumes/create"),
        ("GET", "/images/json"),
        ("GET", "/info"),
        ("GET", "/volumes"),
        ("GET", "/networks"),
    ],
)
def test_proxy_refuses_writes_and_non_container_reads(method, path):
    assert _call(method, path, b"{}" if method != "GET" else None) == 403


def test_proxy_allows_container_reads():
    assert _call("GET", "/containers/json?all=1") == 200


def test_sdk_write_is_refused():
    client = docker.DockerClient(base_url="tcp://127.0.0.1:2375", timeout=10)
    with pytest.raises((APIError, DockerException)):
        client.containers.create("alpine", command="true")
    assert [c for c in client.containers.list(all=True) if c.name == "evil"] == []


def test_real_collection_when_lab_is_up():
    cfg = EvidenceConfig()
    client = docker.DockerClient(base_url=cfg.docker_url, timeout=10)
    lab = client.containers.list(
        all=True, filters={"label": f"com.docker.compose.project={cfg.compose_project}"}
    )
    if not lab:
        pytest.skip("lab is not up")
    col = EvidenceCollector(cfg).collect_detailed("inc-live", "shop_api", None)
    EvidenceBundle.model_validate(col.bundle.model_dump())
    assert {i.kind for i in col.bundle.items} >= {"health", "config", "compose"}
    assert col.log_format in {"plain", "uvicorn_access", "json", "none"}
    assert len(col.bundle.base_sha) == 40
