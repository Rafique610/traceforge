"""Own app (router not yet registered in main.py), SQLite, and a mocked HTTP layer."""

import io
import json
import urllib.error

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from traceforge.config import Settings, get_settings
from traceforge.database import Base, get_db
from traceforge.github import client
from traceforge.github.router import router
from traceforge.incidents import models  # noqa: F401  (register tables)

URL = "https://github.com/acme/lab/issues/7"


@pytest.fixture
def settings():
    return Settings(github_allowed_owners=["acme"], github_token="ghp_" + "a" * 30)


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db(session_factory):
    with session_factory() as s:
        yield s


@pytest.fixture
def client_(session_factory, settings):
    app = FastAPI()
    app.include_router(router)

    def override():
        with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


@pytest.fixture
def mock_http(monkeypatch):
    """Returns a setter: mock_http(json=..., status=..., exc=...). Records requests."""
    calls = []

    def setup(payload=None, status=200, exc=None):
        def fake(req, timeout):
            calls.append((req, timeout))
            if exc:
                raise exc
            if status != 200:
                raise urllib.error.HTTPError(req.full_url, status, "x", exc_headers, io.BytesIO())
            return 200, {}, json.dumps(payload).encode() if payload is not None else b""

        exc_headers = {}
        setup.headers = exc_headers
        monkeypatch.setattr(client, "_open", fake)
        return calls

    return setup
