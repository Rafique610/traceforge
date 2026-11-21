"""Dependency probes for /health. Each check reports a string, never raises."""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.queue import OrderQueue

logger = logging.getLogger("app.health")


def check_db(session: Session) -> str:
    try:
        session.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        logger.warning("health: dependency check failed: %s", exc)
        return f"down: {type(exc).__name__}"


def check_redis(queue: OrderQueue) -> str:
    try:
        queue.ping()
        return "ok"
    except Exception as exc:
        logger.warning("health: dependency check failed: %s", exc)
        return f"down: {type(exc).__name__}"


def check_worker(queue: OrderQueue) -> str:
    try:
        return "ok" if queue.worker_alive() else "missing"
    except Exception:
        return "unknown"
