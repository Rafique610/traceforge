import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from traceforge.database import engine, get_db
from traceforge.main import app

client = TestClient(app)


def _db_reachable() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


@pytest.mark.skipif(not _db_reachable(), reason="Postgres not running (task db:up)")
def test_health_ok_when_db_up():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["db"] == "up"


def test_health_degraded_when_db_down():
    closed = URL.create("postgresql+psycopg", username="x", host="127.0.0.1", port=1, database="x")
    dead = sessionmaker(bind=create_engine(closed, connect_args={"connect_timeout": 1}))

    def dead_db():
        with dead() as session:
            yield session

    app.dependency_overrides[get_db] = dead_db
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "db": "down", "version": "0.1.0"}


def test_request_id_echoed_and_generated():
    assert client.get("/health", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"] == (
        "abc-123"
    )
    generated = client.get("/health", headers={"X-Request-ID": "bad id!\t"}).headers["x-request-id"]
    assert len(generated) == 32


def test_oversized_body_413():
    body = "x" * 1_100_000
    res = client.post("/incidents", content=body, headers={"content-type": "application/json"})
    assert res.status_code == 413 and res.json()["detail"] == "request body too large"


def test_unhandled_error_is_generic_500():
    from fastapi import FastAPI

    from traceforge.health.http import RequestHygieneMiddleware, register_error_handlers

    mini = FastAPI()
    mini.add_middleware(RequestHygieneMiddleware)
    register_error_handlers(mini)

    @mini.get("/boom")
    def boom():
        raise RuntimeError("password=hunter2")

    res = TestClient(mini, raise_server_exceptions=False).get("/boom")
    assert res.status_code == 500
    assert "hunter2" not in res.text and res.json()["request_id"] == res.headers["x-request-id"]


def test_config_validation_fails_fast():
    from pydantic import ValidationError

    from traceforge.config import Settings

    with pytest.raises(ValidationError, match="DB_PASSWORD"):
        Settings(env="prod", _env_file=None)
    with pytest.raises(ValidationError, match="CORS"):
        Settings(env="prod", db_password="x", cors_origins=["*"], _env_file=None)
    assert Settings(env="dev", _env_file=None).cors_origins == []
