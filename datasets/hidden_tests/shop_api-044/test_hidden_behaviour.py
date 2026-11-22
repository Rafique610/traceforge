"""Order confirmation jobs: retries, backoff and dead letters."""

from conftest import observe_job


def test_job_1():
    assert observe_job(24, 5) == [True, 4, [1.0, 2.0, 4.0], 1, 0]
