"""Development-only dispatcher for INDEPENDENT LLM requests over three providers.

Providers: "beatapi", "axforge1", "axforge2" (the last only if `axforge.slot2_enabled()`). Each has
its own queue, pacing clock and in-flight limit of one; providers run concurrently. Official work
(`official=True`) is refused: this pool never touches official metrics, and every result row carries
`tier="development"`.

Sending goes through the gateway (`gateway.chat`), which owns the ledgers, the model guards, the
pacing locks and 429 / Retry-After recording (`axforge.record_429`). The pool adds scheduling
on top: it never reimplements a bypass. The send function is injectable (fakes, fake clock).

Failure policy: the first provider failure halts that provider for this run (no retry of the failed
task). Pending tasks that another allowed provider can run stay available to it. A pre-send refusal
because an earlier 429's Retry-After has not elapsed (`Deferred`) is not a failure: nothing was
sent, the provider backs off exponentially with jitter and the task stays pending.
"""

import hashlib
import json
import os
import random
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from traceforge.agent import axforge, beatapi
from traceforge.agent.beatapi import FileLock

PROVIDERS = ("beatapi", "axforge1", "axforge2")
TIER = "development"


class PoolRefused(RuntimeError):
    """The task may not go through the pool (official work)."""


class Deferred(RuntimeError):
    """A send function raises this when nothing was sent (Retry-After pending). Not a failure."""

    def __init__(self, reason: str, retry_after: float | None = None):
        super().__init__(reason)
        self.retry_after = retry_after


@dataclass
class Task:
    task_id: str  # provider-independent identity: hashed into the idempotency key
    messages: list[dict[str, Any]]
    allow_axforge: bool = False
    official: bool = False
    max_tokens: int | None = None

    @property
    def key(self) -> str:
        return hashlib.sha256(self.task_id.encode("utf-8")).hexdigest()[:24]


@dataclass
class Reply:
    content: str | None
    tokens_in: int = 0
    tokens_out: int = 0
    model: str | None = None


SendFn = Callable[[str, Task], Reply]


@dataclass
class _Prov:
    name: str
    model: str
    interval: float
    ready_at: float = 0.0
    inflight: bool = False
    halted: str | None = None
    deferrals: int = 0
    queue: deque = field(default_factory=deque)
    requests: int = 0
    failures: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    latencies: list = field(default_factory=list)
    starts: list = field(default_factory=list)
    first_start: float | None = None
    last_done: float | None = None


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, max(0, round(q * (len(s) - 1))))]


def default_send(provider: str, task: Task) -> Reply:
    """The real path: gateway.chat with the provider's settings (ledgers/pacing/halt live there)."""
    from traceforge.agent import gateway
    from traceforge.config import get_settings

    base = get_settings()
    if provider == "beatapi":
        update = {"llm_provider": "beatapi", "llm_model": beatapi.FREE_MODEL}
    else:
        slot = provider.removeprefix("axforge")
        update = {"llm_provider": "axforge", "llm_model": axforge.MODEL, "axforge_key_slot": slot}
    s = base.model_copy(update=update)
    try:
        r = gateway.chat(task.messages, settings=s, max_tokens=task.max_tokens)
    except gateway.GatewayError as e:
        if isinstance(e.__cause__, axforge.AxForgeRateLimited):
            raise Deferred(str(e)) from e
        raise
    return Reply(r.content, r.tokens_in, r.tokens_out, r.model)


class Pool:
    def __init__(
        self,
        results_path: Path,
        send: SendFn = default_send,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        wall: Callable[[], float] = time.time,
        rng: random.Random | None = None,
        slot2_enabled: Callable[[], bool] | None = None,
        halted_probe: Callable[[str], str | None] | None = None,
        jitter_max: float = 2.0,
        backoff_cap: float = 600.0,
        max_deferrals: int = 8,
        poll_s: float = 0.5,
    ):
        self.results_path = Path(results_path)
        self._send, self._clock, self._sleep, self._wall = send, clock, sleep, wall
        self._rng = rng or random.Random()
        self._jitter, self._cap, self._max_def, self._poll = (
            jitter_max,
            backoff_cap,
            max_deferrals,
            poll_s,
        )
        self._probe = halted_probe or _default_probe
        enabled = (slot2_enabled or axforge.slot2_enabled)()
        self.providers: dict[str, _Prov] = {
            "beatapi": _Prov("beatapi", beatapi.FREE_MODEL, beatapi.MIN_INTERVAL_S),
            "axforge1": _Prov("axforge1", axforge.MODEL, axforge.MIN_START_INTERVAL_S),
        }
        if enabled:
            self.providers["axforge2"] = _Prov(
                "axforge2", axforge.MODEL, axforge.MIN_START_INTERVAL_S
            )
        self._lock = threading.RLock()
        self._pending: dict[str, Task] = {}
        self._done: set[str] = self._load_done()
        self.unrouted: list[str] = []

    # ---- results file (idempotency) ------------------------------------------------------------
    def _load_done(self) -> set[str]:
        done: set[str] = set()
        try:
            for line in self.results_path.read_text("utf-8").splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue  # a torn last line from an interrupted write is ignored
                if row.get("ok") and row.get("key"):
                    done.add(row["key"])
        except FileNotFoundError:
            pass
        return done

    def _append(self, row: dict) -> None:
        self.results_path.parent.mkdir(parents=True, exist_ok=True)
        with self.results_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
            f.flush()
            os.fsync(f.fileno())

    # ---- submission / routing ------------------------------------------------------------------
    def submit(self, task: Task) -> bool:
        """Queue a task. True if queued; False if already done or already queued (idempotent)."""
        if task.official:
            raise PoolRefused(
                f"task {task.task_id!r} is official: the pool never runs official work"
            )
        with self._lock:
            if task.key in self._done or task.key in self._pending:
                return False
            self._pending[task.key] = task
            for name, p in self.providers.items():
                if name == "beatapi" or task.allow_axforge:
                    p.queue.append(task.key)
            return True

    def _eligible(self, p: _Prov, task: Task) -> bool:
        return p.name == "beatapi" or task.allow_axforge

    def _is_halted(self, p: _Prov) -> bool:
        if p.halted is None and (why := self._probe(p.name)):
            p.halted = f"gateway halt: {why}"
        return p.halted is not None

    def _claim(self, p: _Prov, now: float) -> Task | None:
        """Next task for this provider if it may start now (lock held by caller)."""
        if p.inflight or self._is_halted(p) or p.ready_at > now:
            return None
        if p.name != "beatapi":  # spill only when BeatAPI cannot take the work itself right now
            b = self.providers["beatapi"]
            if not (self._is_halted(b) or b.inflight or b.ready_at > now) and b.queue:
                if any(k in self._pending for k in b.queue):
                    return None
        while p.queue:
            key = p.queue.popleft()
            task = self._pending.pop(key, None)
            if task is not None:
                p.inflight = True
                return task
        return None

    def _has_work(self, p: _Prov) -> bool:
        return not self._is_halted(p) and any(k in self._pending for k in p.queue)

    # ---- execution -----------------------------------------------------------------------------
    def _execute(self, p: _Prov, task: Task) -> None:
        start = self._clock()
        with self._lock:
            p.starts.append(start)
            p.first_start = start if p.first_start is None else p.first_start
        if p.name != "beatapi":
            axforge.guard_model(p.model)  # existing guard; the gateway enforces it again
        try:
            reply = self._send(p.name, task)
        except Deferred as e:
            self._on_deferred(p, task, e)
            return
        except Exception as e:  # first failure halts the provider; the task is not retried
            self._on_failure(p, task, start, e)
            return
        end = self._clock()
        row = {
            "key": task.key,
            "task_id": task.task_id,
            "ok": True,
            "tier": TIER,
            "provider": p.name,
            "model": reply.model or p.model,
            "content": reply.content,
            "tokens_in": reply.tokens_in,
            "tokens_out": reply.tokens_out,
            "latency_s": end - start,
            "ts": self._wall(),
        }
        with self._lock:
            self._append(row)  # saved immediately: an interruption loses at most the one in flight
            self._done.add(task.key)
            p.requests += 1
            p.tokens_in += reply.tokens_in
            p.tokens_out += reply.tokens_out
            p.latencies.append(end - start)
            p.last_done = end
            p.deferrals = 0
            p.ready_at = start + p.interval + self._rng.uniform(0.0, self._jitter)
            p.inflight = False

    def _on_deferred(self, p: _Prov, task: Task, e: Deferred) -> None:
        with self._lock:
            now = self._clock()
            p.deferrals += 1
            p.inflight = False
            self._pending[task.key] = task  # nothing was sent: the task stays pending
            p.queue.appendleft(task.key)
            if p.deferrals > self._max_def:
                p.halted = f"deferred {p.deferrals} times: {e}"
                return
            back = min(self._cap, p.interval * 2 ** (p.deferrals - 1))
            back = max(back, e.retry_after or 0.0)
            p.ready_at = now + back + self._rng.uniform(0.0, self._jitter)

    def _on_failure(self, p: _Prov, task: Task, start: float, e: Exception) -> None:
        end = self._clock()
        with self._lock:
            p.halted = f"{type(e).__name__}: {e}"[:300]
            p.failures += 1
            p.inflight = False
            p.last_done = end
            self._append(
                {
                    "key": task.key,
                    "task_id": task.task_id,
                    "ok": False,
                    "tier": TIER,
                    "provider": p.name,
                    "model": p.model,
                    "error": p.halted,
                    "latency_s": end - start,
                    "ts": self._wall(),
                }
            )

    # ---- run loops -----------------------------------------------------------------------------
    def run(self, threaded: bool = True) -> dict:
        """Run until no provider can make progress. One in-flight request per provider; with
        `threaded=True` the providers run concurrently. Holds a lock file beside the results."""
        lock = FileLock(self.results_path.with_suffix(".lock"))
        if not lock.try_acquire():
            raise PoolRefused("another pool run is using this results file")
        try:
            if threaded:
                ts = [
                    threading.Thread(target=self._worker, args=(p,), daemon=True)
                    for p in self.providers.values()
                ]
                for t in ts:
                    t.start()
                for t in ts:
                    t.join()
            else:
                self._run_serial()
        finally:
            lock.release()
        self.unrouted = sorted(t.task_id for t in self._pending.values())
        return self.stats()

    def _worker(self, p: _Prov) -> None:
        while True:
            with self._lock:
                if not self._has_work(p):  # halted, or nothing left this provider may take
                    return
                now = self._clock()
                task = self._claim(p, now)
                wait = self._poll if task is None else 0.0
                if task is None and p.ready_at > now:
                    wait = p.ready_at - now
            if task is not None:
                self._execute(p, task)
            else:
                self._sleep(wait)

    def _run_serial(self) -> None:
        while True:
            progressed = False
            for p in self.providers.values():
                with self._lock:
                    task = self._claim(p, self._clock())
                if task is not None:
                    self._execute(p, task)
                    progressed = True
            if progressed:
                continue
            with self._lock:
                waits = [pp.ready_at for pp in self.providers.values() if self._has_work(pp)]
                if not waits:
                    return
                delay = max(min(waits) - self._clock(), 0.001)
            self._sleep(delay)

    # ---- stats ---------------------------------------------------------------------------------
    def _prov_stats(self, p: _Prov) -> dict:
        span = (p.last_done - p.first_start) if p.first_start is not None and p.last_done else 0.0
        return {
            "provider": p.name,
            "model": p.model,
            "requests": p.requests,
            "tokens_in": p.tokens_in,
            "tokens_out": p.tokens_out,
            "tokens": p.tokens_in + p.tokens_out,
            "latency_s": list(p.latencies),
            "latency_p50_s": _pct(p.latencies, 0.5),
            "latency_p95_s": _pct(p.latencies, 0.95),
            "failures": p.failures,
            "halted": p.halted,
            "rpm": (p.requests / span * 60.0) if span > 0 else None,
        }

    def stats(self) -> dict:
        per = {n: self._prov_stats(p) for n, p in self.providers.items()}
        lat = [x for p in self.providers.values() for x in p.latencies]
        firsts = [p.first_start for p in self.providers.values() if p.first_start is not None]
        lasts = [p.last_done for p in self.providers.values() if p.last_done is not None]
        span = (max(lasts) - min(firsts)) if firsts and lasts else 0.0
        reqs = sum(s["requests"] for s in per.values())
        return {
            "tier": TIER,
            "providers": per,
            "combined": {
                "requests": reqs,
                "tokens_in": sum(s["tokens_in"] for s in per.values()),
                "tokens_out": sum(s["tokens_out"] for s in per.values()),
                "failures": sum(s["failures"] for s in per.values()),
                "latency_p50_s": _pct(lat, 0.5),
                "latency_p95_s": _pct(lat, 0.95),
                "rpm": (reqs / span * 60.0) if span > 0 else None,
            },
            "pending": sorted(t.task_id for t in self._pending.values()),
        }


def _default_probe(name: str) -> str | None:
    if name == "beatapi":
        return beatapi.halted()
    return axforge.halted(name.removeprefix("axforge"))
