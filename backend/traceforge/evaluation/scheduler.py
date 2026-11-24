"""Job-level scheduler for two AxForge key slots (not a per-request proxy; no research change).

A Job is one runner invocation (command-line args of `traceforge.evaluation.runner`) for one chain
stage. The scheduler keeps one queue per key slot, runs ONE job per slot at a time (so each key
stays
inside its own 30 s request pacing, enforced again by axforge.pace) and runs the two slots
concurrently. It only decides which key runs which job; every request still passes the per-slot
billing gate, ledger, ceilings and pacing inside the runner process.

Rules:
* done-check: a job whose expected records already exist (a glob with at least `min_records`
  matches, or a callable) is marked done without running: finished work is never duplicated, and a
  failed run resumes (the runner skips finished cases) without redoing them.
* dependencies: a job starts only after every job it depends on finished OK (or was already done).
* slot: a job is pinned to "1" or "2", or is "auto" (any healthy slot).

Failure policy (a deliberate reading of the owner's rules: first failure stops use of a key, no
automatic retries, failover only for work that has not started):
* a job that exits non-zero (or whose runner raises) is marked `failed` and its slot is marked
  `halted` (cooling); the failed job is NEVER retried automatically: it stays failed until a person
  resumes deliberately (`retry_failed=True` / `--retry-failed`, which re-queues it; the runner then
  continues from its saved records);
* pending jobs not yet started that are eligible (slot "auto", dependencies satisfied) are routed
  to the other, healthy slot; jobs pinned to a halted slot stay pending;
* a Retry-After recorded for a slot (its pacing state `blocked_until`) keeps that slot cooling until
  it elapses, without marking it halted; the scheduler waits for it if work is left for that slot;
* halted flags are not carried over a scheduler restart (a restart is a deliberate act); job states
  are, and a job found `running` after a kill goes back to `pending` (the runner resumes it).

State (job status, slot, timestamps, exit codes) is written atomically to a JSON file after every
change. A file lock refuses two schedulers at once. No key value is ever read or written here.
"""

import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from traceforge.agent import axforge
from traceforge.agent.beatapi import FileLock

SLOTS = ("1", "2")
PENDING, RUNNING, DONE, FAILED = "pending", "running", "done", "failed"
CommandRunner = Callable[[list[str], str], int]  # (job args, slot) -> exit code


class SchedulerBusy(RuntimeError):
    """Another scheduler holds the lock."""


@dataclass
class Job:
    id: str
    args: list[str]
    deps: list[str] = field(default_factory=list)
    slot: str = "auto"  # "1", "2" or "auto"
    done_glob: str | None = None  # relative to the scheduler base_dir
    min_records: int = 1
    done_check: Callable[[], bool] | None = None


def validate(jobs: list[Job]) -> None:
    ids = [j.id for j in jobs]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate job ids")
    for j in jobs:
        if j.slot not in ("auto", *SLOTS):
            raise ValueError(f"job {j.id}: slot must be 'auto', '1' or '2'")
        if "--axforge-key" in j.args:
            raise ValueError(f"job {j.id}: the scheduler sets --axforge-key itself")
        for d in j.deps:
            if d not in ids:
                raise ValueError(f"job {j.id}: unknown dependency {d!r}")
    seen: set[str] = set()
    by_id = {j.id: j for j in jobs}

    def visit(i: str, path: tuple[str, ...]) -> None:
        if i in path:
            raise ValueError(f"dependency cycle through {i!r}")
        if i in seen:
            return
        for d in by_id[i].deps:
            visit(d, (*path, i))
        seen.add(i)

    for j in jobs:
        visit(j.id, ())


def subprocess_runner(backend: Path, log_dir: Path) -> CommandRunner:
    """Run one job as a child process of the real runner; output goes to a per-job log file."""

    def run(args: list[str], slot: str) -> int:
        log_dir.mkdir(parents=True, exist_ok=True)
        name = "".join(c if c.isalnum() or c in "-_." else "_" for c in " ".join(args)[:60])
        cmd = [sys.executable, "-m", "traceforge.evaluation.runner", *args, "--axforge-key", slot]
        with (log_dir / f"slot{slot}_{name}.log").open("a", encoding="utf-8") as out:
            return subprocess.run(cmd, cwd=backend, stdout=out, stderr=subprocess.STDOUT).returncode

    return run


class Scheduler:
    def __init__(
        self,
        jobs: list[Job],
        state_path: Path,
        runner: CommandRunner,
        *,
        base_dir: Path = Path("."),
        slots: tuple[str, ...] = SLOTS,
        retry_failed: bool = False,
        now: Callable[[], float] = time.time,
        poll_s: float = 1.0,
        pacing_file: Callable[[str], Path] = axforge.pacing_path,
        log: Callable[[str], None] = print,
    ):
        validate(jobs)
        self.jobs = {j.id: j for j in jobs}
        self.order = [j.id for j in jobs]
        self.state_path, self.runner, self.base_dir = Path(state_path), runner, Path(base_dir)
        self.slots, self.now, self.poll_s, self.log = slots, now, poll_s, log
        self.pacing_file = pacing_file
        self.cond = threading.Condition()
        self.halted: dict[str, str] = {}  # slot -> reason (in memory: reset on restart)
        self.running: dict[str, str] = {}  # slot -> job id
        self.state: dict[str, dict] = {i: {"status": PENDING, "slot": None} for i in self.order}
        self._load(retry_failed)

    # ---- state -----------------------------------------------------------------------------
    def _load(self, retry_failed: bool) -> None:
        try:
            saved = json.loads(self.state_path.read_text("utf-8")).get("jobs", {})
        except (OSError, ValueError):
            saved = {}
        for i, st in saved.items():
            if i not in self.state:
                continue
            if st.get("status") == RUNNING:  # killed mid-run: the runner resumes from its records
                st = {**st, "status": PENDING, "interrupted": True}
            if st.get("status") == FAILED and retry_failed:
                st = {**st, "status": PENDING, "retried": True}
            self.state[i] = st

    def _save(self) -> None:
        doc = {
            "version": 1,
            "updated_at": self.now(),
            "slots": {
                s: {"halted": self.halted.get(s), "running": self.running.get(s)}
                for s in self.slots
            },
            "jobs": self.state,
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_name(self.state_path.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        os.replace(tmp, self.state_path)

    # ---- eligibility -------------------------------------------------------------------------
    def _is_done_on_disk(self, j: Job) -> bool:
        if j.done_check is not None:
            return bool(j.done_check())
        if j.done_glob:
            return sum(1 for _ in self.base_dir.glob(j.done_glob)) >= j.min_records
        return False

    def _blocked_until(self, slot: str) -> float:
        try:
            return float(axforge._read_pacing(self.pacing_file(slot)).get("blocked_until") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _slot_ok(self, slot: str) -> bool:
        return slot not in self.halted and self._blocked_until(slot) <= self.now()

    def _deps_ok(self, j: Job) -> bool:
        return all(self.state[d]["status"] == DONE for d in j.deps)

    def _refresh_done(self) -> None:
        changed = False
        for i in self.order:
            st = self.state[i]
            if st["status"] == PENDING and self._is_done_on_disk(self.jobs[i]):
                self.state[i] = {**st, "status": DONE, "skipped": True, "finished_at": self.now()}
                changed = True
        if changed:
            self._save()

    def _next_for(self, slot: str) -> str | None:
        for i in self.order:
            j = self.jobs[i]
            if self.state[i]["status"] == PENDING and self._deps_ok(j) and j.slot in ("auto", slot):
                return i
        return None

    # ---- execution -----------------------------------------------------------------------------
    def _work(self, slot: str, job_id: str) -> None:
        try:
            code = int(self.runner(self.jobs[job_id].args, slot))
        except BaseException as e:  # a crashing runner is a failed job (type only, no details)
            code = -1
            self.log(f"job {job_id}: runner raised {type(e).__name__}")
        with self.cond:
            ok = code == 0
            self.state[job_id] = {
                **self.state[job_id],
                "status": DONE if ok else FAILED,
                "exit_code": code,
                "finished_at": self.now(),
            }
            del self.running[slot]
            if not ok:
                self.halted[slot] = f"job {job_id} exit {code}"
                self.log(f"job {job_id} failed (exit {code}): slot {slot} halted, not retried")
            self._save()
            self.cond.notify_all()

    def run(self) -> dict:
        lock = FileLock(self.state_path.with_suffix(".lock"))
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if not lock.try_acquire():
            raise SchedulerBusy(f"another scheduler holds {lock.path}")
        threads: list[threading.Thread] = []
        try:
            with self.cond:
                self._save()
                while True:
                    self._refresh_done()
                    for slot in self.slots:
                        if slot in self.running or not self._slot_ok(slot):
                            continue
                        i = self._next_for(slot)
                        if i is None:
                            continue
                        self.state[i] = {
                            **self.state[i],
                            "status": RUNNING,
                            "slot": slot,
                            "started_at": self.now(),
                        }
                        self.running[slot] = i
                        self._save()
                        t = threading.Thread(target=self._work, args=(slot, i), daemon=True)
                        threads.append(t)
                        t.start()
                    if not self.running and not self._waiting_for_cooldown():
                        break
                    self.cond.wait(timeout=self.poll_s)
        finally:
            for t in threads:
                t.join()
            lock.release()
        return self.summary()

    def _waiting_for_cooldown(self) -> bool:
        """True if a Retry-After (not a halt) is all that keeps startable work from starting."""
        for slot in self.slots:
            if slot in self.halted or self._blocked_until(slot) <= self.now():
                continue
            if self._next_for(slot) is not None:
                return True
        return False

    def summary(self) -> dict:
        by = {}
        for i in self.order:
            by.setdefault(self.state[i]["status"], []).append(i)
        return {"jobs": by, "halted_slots": dict(self.halted)}

    # ---- dry run ---------------------------------------------------------------------------------
    def plan(self) -> list[dict]:
        """The order and slot each job would get (no job is run; no state is written)."""
        load = {s: 0 for s in self.slots}
        done = {i for i in self.order if self.state[i]["status"] == DONE}
        rows, left = [], [i for i in self.order if i not in done]
        for i in self.order:
            if i in done or self._is_done_on_disk(self.jobs[i]):
                done.add(i)
                if i in left:
                    left.remove(i)
                rows.append({"job": i, "action": "skip (records exist)", "slot": None})
        while left:
            ready = [i for i in left if all(d in done for d in self.jobs[i].deps)]
            if not ready:
                for i in left:
                    rows.append({"job": i, "action": "blocked", "slot": None})
                break
            i = ready[0]
            j = self.jobs[i]
            slot = j.slot if j.slot != "auto" else min(self.slots, key=lambda s: load[s])
            load[slot] = load.get(slot, 0) + 1
            rows.append({"job": i, "action": "run", "slot": slot, "after": j.deps, "args": j.args})
            done.add(i)
            left.remove(i)
        return rows


def load_jobs(path: Path) -> list[Job]:
    """Jobs from a JSON file: {"jobs": [{id, args, deps?, slot?, done_glob?, min_records?}]}."""
    doc = json.loads(Path(path).read_text("utf-8"))
    return [Job(**j) for j in doc["jobs"]]
