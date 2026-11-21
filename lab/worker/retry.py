"""Retry with exponential backoff."""

import logging
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")
log = logging.getLogger("worker.retry")


def with_backoff(fn: Callable[[], T], retries: int, base: float, sleep=time.sleep) -> T:
    """Call fn; on failure retry up to `retries` times, sleeping base * 2**n between tries.

    Total calls = retries + 1. The last exception propagates.
    """
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == retries:
                raise
            delay = base * 2**attempt
            log.info(
                "attempt %s failed (%s); retrying in %.1fs",
                attempt + 1,
                type(exc).__name__,
                delay,
            )
            sleep(delay)
    raise AssertionError("unreachable")
