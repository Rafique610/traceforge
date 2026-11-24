"""BeatAPI free-only profile: the ONLY model that can ever be sent is `glm-5.3-flash-free`.

Why so strict: BeatAPI accounts that hold free credit can also call paid models (e.g. glm-5.3-flash,
glm-5.3, claude-*), so an automated client must never send any other id. These guards are not tied
to `llm_free_only`: they cannot be switched off by a setting.

Safety rules for the shared free account (development tier only):
- one run at a time (`single_instance`, an OS file lock that dies with its process);
- one request in flight machine-wide, at least 90 s after the previous one (`pace`/`stamp_done`);
- pacing state anchored at the repository root, not the working directory;
- the first provider-level failure halts this process's BeatAPI calls (`halt`): no automatic retry.
"""

import contextlib
import json
import os
import sys
import threading
import time
from pathlib import Path

FREE_MODEL = "glm-5.3-flash-free"
BASE_URL = "https://direct.beatapi.io/v1"  # fixed; no fallback host, no configurable URL
MIN_INTERVAL_S = 90.0  # conservative; the documented limit is one successful request a minute
ROOT = Path(__file__).resolve().parents[3]  # repository root: independent of the working directory
STATE_FILE = ROOT / ".cache" / "beatapi_last_request.json"
RUN_LOCK_FILE = ROOT / ".cache" / "beatapi_run.lock"
LEGACY_STATE_FILE = ROOT / "backend" / ".cache" / "beatapi_last_request.json"  # old cwd-relative


class BeatApiRefused(RuntimeError):
    """A request that could cost money or break the pacing rule was refused before sending."""


class BeatApiBusy(RuntimeError):
    """Another process already holds the BeatAPI run lock; this launch must not proceed."""


def guard_model(model: str) -> None:
    """Exact match only: no prefix, suffix, case change, or whitespace tolerance."""
    if model != FREE_MODEL:
        raise BeatApiRefused(
            f"beatapi: only the exact model id '{FREE_MODEL}' may be sent (refused {model!r}); "
            "paid siblings can bill the account"
        )


# --- process-safe file locks -------------------------------------------------------------------
# An OS-level byte lock on an open file: the OS drops it when the holder exits or is killed, so a
# crashed run can never leave a stale lock behind. Holder details are written after byte 16.


class FileLock:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._fd: int | None = None

    def try_acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT)
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        self._fd = fd
        return True

    def acquire(self, poll: float = 0.25) -> None:
        while not self.try_acquire():
            time.sleep(poll)

    def write_info(self, text: str) -> None:
        if self._fd is not None:
            os.lseek(self._fd, 16, os.SEEK_SET)
            os.write(self._fd, text.encode("utf-8")[:200].ljust(200))

    def release(self) -> None:
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def holder_info(path: Path | None = None) -> str:
    try:
        raw = (path or RUN_LOCK_FILE).read_bytes()[16:]
        return raw.decode("utf-8", "replace").strip() or "unknown holder"
    except OSError:
        return "unknown holder"


@contextlib.contextmanager
def single_instance(path: Path | None = None, label: str = ""):
    """Hold for the whole BeatAPI run. A second launch fails at once, naming the holder."""
    lock = FileLock(path or RUN_LOCK_FILE)
    if not lock.try_acquire():
        raise BeatApiBusy(
            "another BeatAPI run is already active ("
            + holder_info(lock.path)
            + "); this launch was refused and made no request"
        )
    try:
        lock.write_info(f"pid={os.getpid()} started={int(time.time())} {label}")
        yield lock
    finally:
        lock.release()


# --- pacing ------------------------------------------------------------------------------------
# One request slot shared by every process: pace() takes it, stamp_done() frees it. At most one
# BeatAPI request is in flight machine-wide, and the next starts >= MIN_INTERVAL_S after the
# previous one finished (or was sent, whichever is later).

_slot_thread = threading.Lock()
_slot_owner: int | None = None
_slot_file: FileLock | None = None


def seconds_until_allowed(now: float | None = None, state_file: Path | None = None) -> float:
    """Seconds to wait. BeatAPI counts its window from when a request finished, so the later of
    "sent" and "finished" is the reference (a slow generation must not shorten it)."""
    path = state_file or STATE_FILE
    now = time.time() if now is None else now
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        last = max(float(state.get("sent_at", 0.0)), float(state.get("done_at", 0.0)))
    except (OSError, ValueError):
        return 0.0
    return max(0.0, last + MIN_INTERVAL_S - now)


def _read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.replace(tmp, path)


def pace(sleep=None, now=None, state_file: Path | None = None) -> float:
    """Take the machine-wide request slot, wait out the interval, stamp the send time.

    The slot stays held until `stamp_done()`. Returns the seconds waited."""
    global _slot_owner, _slot_file
    sleep = sleep or time.sleep  # resolved at call time so tests/callers can patch `time`
    now = now or time.time
    path = state_file or STATE_FILE
    if _slot_owner == threading.get_ident():  # this thread never finished its previous request
        stamp_done(now=now, state_file=path)
    _slot_thread.acquire()
    lock = FileLock(path.with_suffix(".lock"))
    try:
        lock.acquire()
    except BaseException:
        _slot_thread.release()
        raise
    _slot_owner, _slot_file = threading.get_ident(), lock
    wait = seconds_until_allowed(now(), path)
    if wait > 0:
        sleep(wait)
    state = _read_state(path)
    state["sent_at"] = now()  # stamped before sending, so a failed request keeps the spacing
    _write_state(path, state)
    return wait


def stamp_done(now=None, state_file: Path | None = None) -> None:
    """Record when a request finished (success or error), then free the request slot."""
    global _slot_owner, _slot_file
    path = state_file or STATE_FILE
    now = now or time.time
    state = _read_state(path)
    state["done_at"] = now()
    _write_state(path, state)
    if _slot_file is not None:
        lock, _slot_file, _slot_owner = _slot_file, None, None
        lock.release()
        _slot_thread.release()


# --- the first failure halts the provider --------------------------------------------------------
_halt_reason: str | None = None


def halt(reason: str) -> None:
    """After the first provider-level failure nothing more is sent from this process."""
    global _halt_reason
    _halt_reason = _halt_reason or reason


def halted() -> str | None:
    return _halt_reason


def reset_halt() -> None:
    global _halt_reason
    _halt_reason = None


def _migrate_legacy() -> None:
    """Carry the old cwd-relative pacing state over once, so the interval is not forgotten."""
    try:
        if LEGACY_STATE_FILE.is_file() and not STATE_FILE.exists():
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_bytes(LEGACY_STATE_FILE.read_bytes())
    except OSError:
        pass


_migrate_legacy()


# Development-only usage ledger (BeatAPI results are never official research results).
LEDGER = Path(__file__).resolve().parents[3] / "runs" / "beatapi_usage.jsonl"


def record_usage(usage, *, path: Path | None = None) -> None:
    p = path or LEDGER
    pt, ct = getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None)
    row = {"ts": time.time(), "tier": "development", "model": FREE_MODEL}
    row.update(
        {"input_tokens": pt, "output_tokens": ct, "usage_source": "provider"}
        if pt is not None and ct is not None
        else {"usage_source": "unknown"}
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + chr(10))
