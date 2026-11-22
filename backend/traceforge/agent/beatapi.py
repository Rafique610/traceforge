"""BeatAPI free-only profile: the ONLY model that can ever be sent is `glm-5.3-flash-free`.

Why so strict: BeatAPI accounts that hold free credit can also call paid models (e.g. glm-5.3-flash,
glm-5.3, claude-*), so an automated client must never send any other id. These guards are not tied
to `llm_free_only`: they cannot be switched off by a setting.

Pacing: the free id allows 1 successful request per minute per account (before a first top-up).
`pace()` enforces a minimum 65 s between live requests, across processes, using a timestamp file.
"""

import json
import time
from pathlib import Path

FREE_MODEL = "glm-5.3-flash-free"
BASE_URL = "https://direct.beatapi.io/v1"  # fixed; no fallback host, no configurable URL
MIN_INTERVAL_S = 65.0
STATE_FILE = Path(".cache/beatapi_last_request.json")


class BeatApiRefused(RuntimeError):
    """A request that could cost money or break the pacing rule was refused before sending."""


def guard_model(model: str) -> None:
    """Exact match only: no prefix, suffix, case change, or whitespace tolerance."""
    if model != FREE_MODEL:
        raise BeatApiRefused(
            f"beatapi: only the exact model id '{FREE_MODEL}' may be sent (refused {model!r}); "
            "paid siblings can bill the account"
        )


def seconds_until_allowed(now: float | None = None, state_file: Path | None = None) -> float:
    path = state_file or STATE_FILE
    now = time.time() if now is None else now
    try:
        last = float(json.loads(path.read_text(encoding="utf-8")).get("sent_at", 0.0))
    except (OSError, ValueError):
        return 0.0
    return max(0.0, last + MIN_INTERVAL_S - now)


def pace(sleep=None, now=None, state_file: Path | None = None) -> float:
    """Block until 65 s have passed since the previous live request, then stamp this one.

    Stamping happens before sending, so even a failed request keeps the spacing (conservative).
    Returns the number of seconds waited."""
    sleep = sleep or time.sleep  # resolved at call time so tests/callers can patch `time`
    now = now or time.time
    path = state_file or STATE_FILE
    wait = seconds_until_allowed(now(), path)
    if wait > 0:
        sleep(wait)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"sent_at": now()}), encoding="utf-8")
    return wait
