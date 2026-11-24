"""AxForge profile: only `glm-5.3-flash` on the fixed base URL, one attempt, no fallback.

The website host is `glm-5-3-flash.axforge.ai`; the API model id is `glm-5.3-flash` (with a dot).
The same key can call other (prepaid) models, and AxForge exposes no field that separates the free
allowance from paid balance, so the id and host are locked here and every error stops the caller.

Budget guard (not switchable by a setting): every live request is recorded in a persistent ledger
with the token counts the provider reported. Before each request the cumulative total is read back;
at SAFETY_CEILING tokens (the whole 3M free allowance, by the owner's authorization of
24 Nov 2026) all requests are refused. If the ledger
cannot be read, or holds a request whose usage is unknown, requests are refused as well.

Billing gate (not switchable by a setting, default, retry or worker): no request is ever sent in a
process that has not been explicitly authorized with `authorize()`. The owner must first confirm on
the AxForge dashboard that the balance is free allowance only and auto top-up is off; the runner's
`--axforge-billing-verified` flag is that confirmation. Authorization lives in memory of one
process only (never an environment variable or file), so a child or worker process starts without
it, and it is written to the usage ledger as an audit row.

Two keys (slots). Slot "1" is AXFORGE_API_KEY with the original ledger/pacing/halt state; slot "2"
is AXFORGE_API_KEY2 with its own files (`*_k2`), its own in-flight reservation, 30 s pacing clock,
429/Retry-After block and first-failure halt. Each slot has its own ceiling (ALLOWANCE) and, once
slot 2 is enabled, COMBINED_CEILING bounds the sum. Slot 2 is disabled unless the env var
AXFORGE_API_KEY2 is set AND runs/axforge_keys_verified.json holds {"slot2_enabled": true}. Only the
slot NAME is ever written anywhere; key values are read by config.Settings and never stored.
The other slot's in-flight reservation is only visible inside one process; across processes the
combined check relies on the other ledger (margin: one request's worst case).
"""

import email.utils
import json
import os
import random
import re
import threading
import time
from pathlib import Path

from traceforge.agent.beatapi import FileLock  # the OS byte-lock primitive only; no BeatAPI rule

MODEL = "glm-5.3-flash"
BASE_URL = "https://api.axforge.ai/v1"  # fixed; no configurable URL, no fallback host
ALLOWANCE = 3_000_000
# Owner authorization (24 Nov 2026): the former 600k reserve may be spent: the ceiling is the whole
# free allowance. No request that could cross it (committed + input estimate + max output) is sent.
SAFETY_CEILING = ALLOWANCE  # was 2_400_000 (80%) until 24 Nov 2026
# Anchored at the repository root, not the working directory, so the count survives restarts.
LEDGER = Path(__file__).resolve().parents[3] / "runs" / "axforge_usage.jsonl"
LEDGER2 = Path(__file__).resolve().parents[3] / "runs" / "axforge_usage_k2.jsonl"
COMBINED_CEILING = 4_800_000  # planning ceiling across both keys, applies when slot 2 is enabled
ENABLE_MARKER = Path(__file__).resolve().parents[3] / "runs" / "axforge_keys_verified.json"
SLOTS = ("1", "2")
_lock = threading.Lock()
_inflight = 0  # output tokens reserved by requests currently in flight (slot 1)
_k2 = {"inflight": 0, "file": None, "halt": None}  # the same per-process state for slot 2


class AxForgeRefused(RuntimeError):
    """A request that could cost money or break the budget guard was refused before sending."""


def _slot(slot) -> str:
    slot = str(slot)
    if slot not in SLOTS:
        raise AxForgeRefused(f"axforge: unknown key slot {slot!r} (use '1' or '2')")
    return slot


def ledger_path(slot="1") -> Path:
    return LEDGER if _slot(slot) == "1" else LEDGER2


def pacing_path(slot="1") -> Path:
    return PACING_FILE if _slot(slot) == "1" else PACING_FILE2


def slot2_enabled() -> bool:
    """Owner switch: the key is configured AND the coordinator wrote the verification marker."""
    try:
        from traceforge.config import Settings

        if not Settings().axforge_api_key2.get_secret_value():
            return False
        return json.loads(ENABLE_MARKER.read_text("utf-8")).get("slot2_enabled") is True
    except (OSError, ValueError, AttributeError):
        return False


def require_slot(slot="1") -> str:
    slot = _slot(slot)
    if slot == "2" and not slot2_enabled():
        raise AxForgeRefused(
            "axforge: key slot 2 is disabled (needs AXFORGE_API_KEY2 and "
            f"{ENABLE_MARKER.name} with slot2_enabled=true written by the owner). No request sent."
        )
    return slot


def _inflight_of(slot) -> int:
    return _inflight if slot == "1" else _k2["inflight"]


def _add_inflight(slot, n: int) -> None:
    global _inflight
    if slot == "1":
        _inflight = max(0, _inflight + n)
    else:
        _k2["inflight"] = max(0, _k2["inflight"] + n)


NOT_AUTHORIZED = (
    "AXFORGE REFUSED: this process is not authorized to call AxForge. AxForge can bill the account "
    "and its free-versus-paid status cannot be checked through the API. Before any run the owner "
    "must confirm on the AxForge dashboard that (1) only free allowance is in use and (2) auto "
    "top-up is OFF, then pass --axforge-billing-verified. No request was sent."
)
_authorized_by: str | None = None  # in-process only; never inherited by child processes


# Pacing: 2 requests per minute. At least MIN_START_INTERVAL_S must pass between the START of any
# two AxForge requests, machine-wide: the last start time lives in a shared state file guarded by an
# OS-level byte lock, so parallel workers, separate processes and resumed runs all share one clock.
# At most one request is in flight machine-wide (the lock is held until the request finishes).
# The limit is undocumented by the provider; history (see docs) shows 429s 10 to 11 s after a
# success, i.e. at the old 10 s completion-based gap.
MIN_START_INTERVAL_S = 30.0
PACING_FILE = Path(__file__).resolve().parents[3] / "runs" / "axforge_pacing.json"
PACING_FILE2 = Path(__file__).resolve().parents[3] / "runs" / "axforge_pacing_k2.json"
JITTER_MAX_S = 3.0  # random extra wait (two-key mode only) so the two chains never synchronize
_slot_thread = threading.Lock()  # one request per process at a time (the OS lock is per process)
_slot_thread2 = threading.Lock()
_slot_file: FileLock | None = None
_rng = random.Random()


class AxForgeRateLimited(RuntimeError):
    """A previous 429 carried a Retry-After that has not elapsed: refused before any request."""


def _read_pacing(path: Path) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {"corrupt": True}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return {"corrupt": True}  # unreadable state: fail closed (wait the full interval)


def _write_pacing(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.replace(tmp, path)


def seconds_until_allowed(now: float, state: dict) -> float:
    """Seconds until the next request may START (0 if now). A wall-clock jump backwards can never
    make this longer than one interval."""
    if state.get("corrupt"):
        return MIN_START_INTERVAL_S
    last = float(state.get("last_start") or 0.0)
    return min(MIN_START_INTERVAL_S, max(0.0, last + MIN_START_INTERVAL_S - now))


def pace(sleep=None, now=None, state_file: Path | None = None, slot="1", rng=None) -> float:
    """Take the machine-wide request slot, wait until MIN_START_INTERVAL_S after the previous
    request STARTED, and stamp this request's start. Returns the seconds waited.

    The slot stays held until `done_turn()`. A Retry-After from an earlier 429 that has not elapsed
    raises AxForgeRateLimited at once (it never sleeps for it) and sends nothing.
    Each key slot has its own state file, lock and clock; with slot 2 enabled a random 0 to
    JITTER_MAX_S is added to the wait."""
    global _slot_file
    slot = require_slot(slot)
    sleep, now = sleep or time.sleep, now or time.time
    path = state_file or pacing_path(slot)
    thread = _slot_thread if slot == "1" else _slot_thread2
    thread.acquire()
    lock = FileLock(path.with_suffix(".lock"))
    try:
        lock.acquire()
        state = _read_pacing(path)
        blocked = float(state.get("blocked_until") or 0.0)
        if blocked and blocked > now():
            raise AxForgeRateLimited(
                "axforge: the last 429 asked to wait until "
                f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(blocked))} (Retry-After "
                f"{state.get('last_429', {}).get('retry_after_s')} s); no request was sent"
            )
        wait = seconds_until_allowed(now(), state)
        if JITTER_MAX_S > 0 and slot2_enabled():
            wait += (rng or _rng).uniform(0.0, JITTER_MAX_S)
        if wait > 0:
            sleep(wait)
        prev = float(state.get("last_start") or 0.0)
        state.pop("corrupt", None)
        state["last_start"] = now()  # stamped BEFORE sending: a failed request keeps the spacing
        _write_pacing(path, state)
        _log_send(path, state["last_start"], prev, wait, slot)
    except BaseException:
        lock.release()
        thread.release()
        raise
    if slot == "1":
        _slot_file = lock
    else:
        _k2["file"] = lock
    return wait


def _log_send(
    path: Path, sent_at: float, prev_start: float, waited: float, slot: str = "1"
) -> None:
    """Append-only record of every request start (audit: proves the start-to-start interval)."""
    row = {"sent_at": sent_at, "prev_start": prev_start or None, "waited_s": round(waited, 3)}
    row["pid"] = os.getpid()
    row["slot"] = slot
    with path.with_suffix(".log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def done_turn(now=None, state_file: Path | None = None, slot="1") -> None:
    """Record when the request finished and free the slot (safe to call more than once)."""
    global _slot_file
    slot = _slot(slot)
    if (_slot_file if slot == "1" else _k2["file"]) is None:
        return
    path = state_file or pacing_path(slot)
    state = _read_pacing(path)
    state.pop("corrupt", None)
    state["last_done"] = (now or time.time)()
    _write_pacing(path, state)
    if slot == "1":
        lock, _slot_file = _slot_file, None
        lock.release()
        _slot_thread.release()
    else:
        lock, _k2["file"] = _k2["file"], None
        lock.release()
        _slot_thread2.release()


_SECRET_HEADER = re.compile(r"(?i)authorization|cookie|api[-_]?key|token|secret|password")
_SECRET_VALUE = re.compile(r"(?i)(bearer\s+\S+|sk-[A-Za-z0-9_\-]{8,})")


def redact_headers(headers) -> dict:
    """Response headers safe to store: secret names dropped, secret-like values masked."""
    out: dict = {}
    for k, v in dict(headers or {}).items():
        if _SECRET_HEADER.search(str(k)):
            continue
        out[str(k).lower()] = _SECRET_VALUE.sub("[redacted]", str(v))[:300]
    return out


def parse_retry_after(value, now: float | None = None) -> float | None:
    """Seconds from a Retry-After header (delta-seconds or an HTTP date); None if absent/invalid."""
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(text)
        return max(0.0, when.timestamp() - (now if now is not None else time.time()))
    except (TypeError, ValueError):
        return None


def record_429(
    exc,
    *,
    now: float | None = None,
    state_file: Path | None = None,
    path: Path | None = None,
    slot="1",
) -> dict:
    """Record a 429: status, time, redacted response headers and Retry-After (ledger row and the
    shared pacing state). A Retry-After blocks further requests until it elapses. Never retries."""
    now = time.time() if now is None else now
    headers = redact_headers(getattr(getattr(exc, "response", None), "headers", None))
    retry = parse_retry_after(headers.get("retry-after"), now)
    info = {
        "http_status": 429,
        "at": now,
        "retry_after_s": retry,
        "headers": headers,
        "error_type": type(exc).__name__,
    }
    record_error(429, path=path, extra={"retry_after_s": retry, "headers": headers}, slot=slot)
    pacing = state_file or pacing_path(slot)
    state = _read_pacing(pacing)
    state.pop("corrupt", None)
    state["last_429"] = info
    if retry is not None:
        state["blocked_until"] = now + retry
    _write_pacing(pacing, state)
    return info


_halt_reason: str | None = None


def halt(reason: str, slot="1") -> None:
    """After the first provider-level failure this process sends nothing more on this key slot."""
    global _halt_reason
    if _slot(slot) == "1":
        _halt_reason = _halt_reason or reason
    else:
        _k2["halt"] = _k2["halt"] or reason


def halted(slot="1") -> str | None:
    return _halt_reason if _slot(slot) == "1" else _k2["halt"]


def reset_halt(slot="1") -> None:
    global _halt_reason
    if _slot(slot) == "1":
        _halt_reason = None
    else:
        _k2["halt"] = None


def is_authorized() -> bool:
    return _authorized_by is not None


def authorize(run_id: str, *, path: Path | None = None, slot="1") -> None:
    """Explicit owner confirmation for THIS process. Recorded in the ledger as an audit row."""
    global _authorized_by
    if not run_id:
        raise AxForgeRefused("axforge: authorization must name the run it is for")
    slot = require_slot(slot)
    if slot == "2" and path is None and not LEDGER2.exists():
        LEDGER2.parent.mkdir(parents=True, exist_ok=True)
        LEDGER2.touch()  # the owner enabled slot 2: its ledger starts empty
    read_ledger(path, slot)  # refuses when the usage ledger is missing or unreadable
    _append(
        {"type": "authorization", "run_id": run_id, "billing_verified_by_owner": True}, path, slot
    )
    _authorized_by = run_id


def revoke() -> None:
    global _authorized_by
    _authorized_by = None


def require_authorization() -> None:
    if _authorized_by is None:
        raise AxForgeRefused(NOT_AUTHORIZED)


def guard_model(model: str) -> None:
    if model != MODEL:  # exact match: no prefix, case change, or the hyphenated website spelling
        raise AxForgeRefused(
            f"axforge: only the exact model id '{MODEL}' may be sent (refused {model!r})"
        )


def read_ledger(path: Path | None = None, slot="1") -> list[dict]:
    p = path or ledger_path(slot)
    if not p.exists():
        raise AxForgeRefused(f"axforge: usage ledger {p} is missing; cumulative usage is unknown")
    try:
        return [json.loads(line) for line in p.read_text("utf-8").splitlines() if line.strip()]
    except (OSError, ValueError) as e:
        raise AxForgeRefused(f"axforge: usage ledger unreadable ({e}); refusing to send") from e


def totals(path: Path | None = None, slot="1") -> dict:
    """Cumulative provider-reported usage. `reliable` is False if any request's usage is unknown."""
    rows = read_ledger(path, slot)
    live = [r for r in rows if r.get("type", "request") == "request"]
    unknown = [r for r in live if r.get("usage_source") == "unknown"]
    # A failed request may still have been processed (timeout, 5xx): its estimated input tokens are
    # counted as used, so a flaky provider can only make the budget look smaller, never larger.
    est = sum(int(r.get("estimated_tokens") or 0) for r in rows if r.get("type") == "error")
    reported = sum(int(r.get("total_tokens") or 0) for r in live)
    return {
        "requests": len(live),
        "input_tokens": sum(int(r.get("input_tokens") or 0) for r in live),
        "output_tokens": sum(int(r.get("output_tokens") or 0) for r in live),
        "total_tokens": reported,
        "estimated_tokens": est,
        "committed_tokens": reported + est,
        "unknown_requests": len(unknown),
        "stopped": any(r.get("type") == "stop" for r in rows),
        "reliable": not unknown,
        "remaining_to_ceiling": SAFETY_CEILING - reported - est,
    }


def _floor_path(path: Path | None, slot="1") -> Path:
    p = path or ledger_path(slot)
    return p.with_name(p.name + ".floor")


def _read_floor(path: Path | None, slot="1") -> int:
    try:
        return int(json.loads(_floor_path(path, slot).read_text("utf-8"))["committed_tokens"])
    except (OSError, ValueError, KeyError):
        return 0


def raise_floor(path: Path | None = None, slot="1") -> int:
    """High-water mark of committed tokens, only ever raised. If the ledger is later truncated,
    edited down or replaced, the total drops below this floor and every request is refused."""
    floor = max(_read_floor(path, slot), totals(path, slot)["committed_tokens"])
    f = _floor_path(path, slot)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps({"committed_tokens": floor}), encoding="utf-8")
    tmp.replace(f)
    return floor


def estimate_input_tokens(kwargs: dict) -> int:
    """Deliberately high estimate (3 characters per token) of what a request will send."""
    body = json.dumps({"m": kwargs.get("messages"), "t": kwargs.get("tools")}, default=str)
    return len(body) // 3 + 1


def _committed_other(slot: str) -> int:
    try:
        return totals(None, slot)["committed_tokens"]
    except AxForgeRefused:
        if slot == "2" and not LEDGER2.exists():
            return 0  # slot 2 never used yet
        raise


def check_budget(
    max_tokens: int, path: Path | None = None, slot="1", other_inflight: int = 0
) -> dict:
    """Refuse unless cumulative usage plus this request's worst case stays under the per-slot
    ceiling and, when slot 2 is enabled, the combined ceiling (both slots plus in-flight)."""
    slot = _slot(slot)
    t = totals(path, slot)
    if t["stopped"]:
        raise AxForgeRefused(
            "axforge: a stop was recorded (billing signal or exhausted); ask the owner"
        )
    if not t["reliable"]:
        raise AxForgeRefused("axforge: a request with unknown usage is in the ledger; stopping")
    floor = _read_floor(path, slot)
    if t["committed_tokens"] < floor:
        raise AxForgeRefused(
            f"axforge: ledger total {t['committed_tokens']:,} is below the high-water mark "
            f"{floor:,}: the ledger was truncated or altered; refusing to send"
        )
    if t["committed_tokens"] + max_tokens >= SAFETY_CEILING:
        raise AxForgeRefused(
            f"axforge: safety ceiling {SAFETY_CEILING:,} tokens reached or would be crossed "
            f"(used {t['committed_tokens']:,}, this request may add up to {max_tokens:,} tokens "
            "counting its estimated input and maximum output)"
        )
    if slot2_enabled():
        other = _committed_other("2" if slot == "1" else "1")
        if t["committed_tokens"] + other + max_tokens + other_inflight >= COMBINED_CEILING:
            raise AxForgeRefused(
                f"axforge: combined ceiling {COMBINED_CEILING:,} tokens reached or would be "
                "crossed "
                f"(both keys used {t['committed_tokens'] + other:,}, this request may add up to "
                f"{max_tokens + other_inflight:,} tokens)"
            )
    return t


def _append(row: dict, path: Path | None, slot="1") -> None:
    p = path or ledger_path(slot)
    p.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "slot": slot, **row}) + "\n")
        raise_floor(p, slot)  # high-water mark follows every row; it can only rise


def record(usage, *, path: Path | None = None, slot="1") -> None:
    """Append one live request with the provider-reported usage (unknown if none was reported)."""
    pt, ct = getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None)
    if pt is None or ct is None:
        _append({"type": "request", "model": MODEL, "usage_source": "unknown"}, path, slot)
        return
    total = getattr(usage, "total_tokens", None) or (pt + ct)
    _append(
        {
            "type": "request",
            "model": MODEL,
            "input_tokens": pt,
            "output_tokens": ct,
            "total_tokens": total,
            "usage_source": "provider",
        },
        path,
        slot,
    )


def record_error(
    status: int | None,
    *,
    estimated_tokens: int = 0,
    path: Path | None = None,
    extra: dict | None = None,
    slot="1",
) -> None:
    """A failed request: no tokens reported. A 402/403 (quota or billing signal) stops all.
    `estimated_tokens` counts as used when the request may have been processed (5xx, timeout)."""
    row = {"type": "error", "model": MODEL, "http_status": status, **(extra or {})}
    if estimated_tokens:
        row["estimated_tokens"] = estimated_tokens
    _append(row, path, slot)
    if status in (402, 403):
        _append({"type": "stop", "reason": f"http {status}"}, path, slot)


def reserve(max_tokens: int, path: Path | None = None, slot="1") -> None:
    """Check the budget counting requests already in flight, then reserve this one's worst case.

    With parallel workers each request could otherwise pass the check against the same ledger total;
    the reservation keeps total + in-flight + this request under the ceiling."""
    slot = require_slot(slot)  # a disabled slot 2 is refused before anything else
    require_authorization()  # first check on every request, whatever the caller
    with _lock:
        other = "2" if slot == "1" else "1"
        check_budget(max_tokens + _inflight_of(slot), path, slot, _inflight_of(other))
        _add_inflight(slot, max_tokens)


def release(max_tokens: int, slot="1") -> None:
    with _lock:
        _add_inflight(_slot(slot), -max_tokens)
