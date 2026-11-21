"""Redis job queue: connect, BRPOP loop, requeue and dead-letter."""

import json
import logging
import time
from collections.abc import Callable

from worker.retry import with_backoff
from worker.settings import WorkerSettings

log = logging.getLogger("worker.queue")
BRPOP_TIMEOUT_S = 5


class MalformedJob(ValueError):
    pass


def make_client(settings: WorkerSettings):
    import redis  # lazy: unit tests inject a fake client

    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        socket_connect_timeout=2,
        socket_timeout=BRPOP_TIMEOUT_S + 5,
        decode_responses=True,
    )


def connect_with_retry(settings: WorkerSettings, factory=make_client, sleep=time.sleep):
    """Ping until the broker answers; log every failed attempt, then give up loudly."""
    client = factory(settings)

    def ping():
        try:
            client.ping()
        except Exception as exc:
            log.warning(
                "redis %s:%s not reachable: %s",
                settings.redis_host,
                settings.redis_port,
                exc,
            )
            raise

    with_backoff(
        ping,
        retries=settings.connect_attempts,
        base=settings.backoff_base_s,
        sleep=sleep,
    )
    return client


def parse_job(raw: str) -> dict:
    try:
        job = json.loads(raw)
        job["order_id"] = int(job["order_id"])
        job["type"]
    except (ValueError, KeyError, TypeError) as exc:
        raise MalformedJob(f"bad job payload: {raw[:80]!r}") from exc
    return job


def pop_job(client, settings: WorkerSettings) -> dict | None:
    """Blocking pop of one job. None on timeout. Malformed payloads are dead-lettered."""
    item = client.brpop(settings.order_queue, timeout=BRPOP_TIMEOUT_S)
    if item is None:
        return None
    _, raw = item
    try:
        return parse_job(raw)
    except MalformedJob:
        log.error("dead-lettering malformed job")
        client.lpush(settings.dead_queue, raw)
        return None


def dead_letter(client, settings: WorkerSettings, job: dict, error: str) -> None:
    client.lpush(settings.dead_queue, json.dumps({**job, "error": error}))


def consume_once(
    client, settings: WorkerSettings, handler: Callable[[dict], None], sleep=time.sleep
) -> bool:
    """Handle at most one job with retries. Returns True if a job was taken from the queue."""
    job = pop_job(client, settings)
    if job is None:
        return False
    try:
        with_backoff(
            lambda: handler(job),
            retries=settings.max_retries,
            base=settings.backoff_base_s,
            sleep=sleep,
        )
    except Exception as exc:
        log.error(
            "job %s failed after %s retries: %s",
            job.get("job_id"),
            settings.max_retries,
            exc,
        )
        dead_letter(client, settings, job, f"{type(exc).__name__}: {exc}")
    return True
