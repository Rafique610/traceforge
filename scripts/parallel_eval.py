"""Thin CLI over traceforge.evaluation.scheduler: run runner jobs on AxForge key slots 1 and 2.

  python scripts/parallel_eval.py --jobs jobs.json [--state runs/scheduler_state.json]
         [--slots 1,2] [--dry-run] [--retry-failed]

jobs.json: {"jobs": [{"id": "l0", "args": ["--manifest", ..., "--axforge-billing-verified"],
"done_glob": "runs/x/l0/records/*.json", "deps": [], "slot": "auto"}]}. Reads no key; the real
requests happen inside the runner processes. See the scheduler module docstring for the policy.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from traceforge.agent import axforge  # noqa: E402
from traceforge.evaluation import scheduler  # noqa: E402


def main(argv: list[str] | None = None, runner: scheduler.CommandRunner | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--jobs", type=Path, required=True)
    ap.add_argument("--state", type=Path, default=ROOT / "runs" / "scheduler_state.json")
    ap.add_argument("--slots", default="1,2", help="key slots to use, e.g. 1 or 1,2")
    ap.add_argument("--base-dir", type=Path, default=ROOT, help="done_glob is relative to this")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, run nothing")
    ap.add_argument("--retry-failed", action="store_true", help="re-queue failed jobs (manual)")
    a = ap.parse_args(argv)
    slots = tuple(s.strip() for s in a.slots.split(",") if s.strip())
    if not slots or any(s not in scheduler.SLOTS for s in slots):
        print("refused: --slots must be 1, 2 or 1,2", file=sys.stderr)
        return 2
    if "2" in slots and not a.dry_run and not axforge.slot2_enabled():
        print("refused: key slot 2 is not enabled by the owner", file=sys.stderr)
        return 2
    sched = scheduler.Scheduler(
        scheduler.load_jobs(a.jobs),
        a.state,
        runner or scheduler.subprocess_runner(BACKEND, a.state.parent / "scheduler_logs"),
        base_dir=a.base_dir,
        slots=slots,
        retry_failed=a.retry_failed,
    )
    if a.dry_run:
        print(json.dumps(sched.plan(), indent=2))
        return 0
    try:
        result = sched.run()
    except scheduler.SchedulerBusy as e:
        print(f"refused: {e}", file=sys.stderr)
        return 3
    print(json.dumps(result, indent=2))
    return 0 if not result["jobs"].get("failed") and not result["jobs"].get("pending") else 1


if __name__ == "__main__":
    sys.exit(main())
