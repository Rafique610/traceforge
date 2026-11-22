"""Reproducer: the health endpoint alternates between healthy and degraded."""


def test_health_alternates(client, queue):
    seen = []
    for alive in (True, False, True, False):
        queue.alive = alive
        seen.append(client.get("/health").status_code)
    assert seen == [200, 503, 200, 503]
