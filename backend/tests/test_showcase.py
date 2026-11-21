from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from traceforge.showcase import add_showcase


def _client(enabled: bool) -> TestClient:
    app = FastAPI()

    @app.get("/x")
    def read() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/x")
    def write() -> dict[str, bool]:
        return {"wrote": True}

    add_showcase(app, SimpleNamespace(showcase_mode=enabled))
    return TestClient(app)


def test_get_allowed_when_enabled():
    assert _client(True).get("/x").status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_writes_blocked_when_enabled(method):
    assert getattr(_client(True), method)("/x").status_code == 403


def test_writes_allowed_when_disabled():
    assert _client(False).post("/x").status_code == 200
