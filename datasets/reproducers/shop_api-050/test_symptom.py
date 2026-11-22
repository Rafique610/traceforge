"""Reproducer: the health endpoint while the job broker is unreachable."""


def test_health_reports_the_broker(real_deps_client):
    r = real_deps_client.get("/health")
    assert r.status_code == 503
    assert r.json()["redis"].startswith("down")
    assert r.json()["db"] == "ok"
