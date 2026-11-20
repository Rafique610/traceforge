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
