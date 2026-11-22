"""Reproducer: the health endpoint while the database is unreachable."""


def test_health_reports_the_database(real_deps_client):
    r = real_deps_client.get("/health")
    assert r.status_code == 503
    assert r.json()["db"].startswith("down")
    assert r.json()["redis"] == "ok"
