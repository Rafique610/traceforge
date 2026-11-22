"""Order confirmation jobs: retries, backoff and dead letters."""

from conftest import observe_job


def test_job_1():
    assert observe_job('not json', 0) == [False, 0, [], 1, 0]
