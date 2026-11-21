"""Job producer: pushes order-confirmation jobs onto the Redis list the worker consumes."""

import json
import time
import uuid
from decimal import Decimal
from functools import lru_cache

from app.settings import get_settings


@lru_cache
def get_client():
    import redis  # imported lazily so unit tests need no broker client

    s = get_settings()
    return redis.Redis(
        host=s.redis_host, port=s.redis_port, socket_connect_timeout=2, socket_timeout=2
    )


class OrderQueue:
    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        return self._client if self._client is not None else get_client()

    def enqueue_confirmation(self, order_id: int, total: Decimal) -> str:
        job = {
            "job_id": uuid.uuid4().hex,
            "type": "order_confirmation",
            "order_id": order_id,
            "total": str(total),
            "attempt": 0,
            "enqueued_at": time.time(),
        }
        self.client.lpush(get_settings().order_queue, json.dumps(job))
        return job["job_id"]

    def ping(self) -> bool:
        return bool(self.client.ping())

    def worker_alive(self) -> bool:
        return bool(self.client.exists("worker:heartbeat"))


def get_queue() -> OrderQueue:
    """FastAPI dependency."""
    return OrderQueue()
