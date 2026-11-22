
import json

from worker.queue import consume_once
from worker.settings import WorkerSettings


class Broker:
    """In-memory stand-in for the three list calls the worker makes (test double)."""

    def __init__(self):
        self.lists = {}

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)

    def brpop(self, key, timeout=0):
        items = self.lists.get(key) or []
        return (key, items.pop()) if items else None


def observe_job(payload, failures):
    settings = WorkerSettings(db_user="worker", db_password="unused")
    broker = Broker()
    raw = payload if isinstance(payload, str) else json.dumps({"job_id": "j", "type": "order_confirmation", "order_id": payload, "total": "1.00"})
    broker.lpush("orders:confirm", raw)
    calls, sleeps = [], []

    def handler(job):
        calls.append(job["order_id"])
        if len(calls) <= failures:
            raise RuntimeError("database busy")

    taken = consume_once(broker, settings, handler, sleep=sleeps.append)
    dead = sum(len(v) for k, v in broker.lists.items() if k.endswith(":dead"))
    return [taken, len(calls), sleeps, dead, len(broker.lists.get("orders:confirm", []))]
