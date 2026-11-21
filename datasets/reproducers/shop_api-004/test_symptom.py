"""Reproducer: the health endpoint intermittently reports the worker as missing."""


def test_health_degraded_when_worker_heartbeat_lapses(client, queue):
    assert client.get("/health").status_code == 200
    queue.alive = False
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["worker"] == "missing"
