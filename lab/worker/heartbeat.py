"""Liveness heartbeat: key `worker:heartbeat` with a 15 s TTL.

`python -m worker.heartbeat` exits 0 if the key exists (used by the container healthcheck).
"""

import sys
import time

HEARTBEAT_KEY = "worker:heartbeat"
HEARTBEAT_TTL_S = 15


def beat(client) -> None:
    client.set(HEARTBEAT_KEY, str(time.time()), ex=HEARTBEAT_TTL_S)


def is_alive(client) -> bool:
    return bool(client.exists(HEARTBEAT_KEY))


if __name__ == "__main__":
    from worker.queue import make_client
    from worker.settings import get_settings

    try:
        sys.exit(0 if is_alive(make_client(get_settings())) else 1)
    except Exception:
        sys.exit(1)
