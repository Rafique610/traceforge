"""Experiment runner: one condition over one split, resumable, freeze-guarded.

ASSUMPTION (isolated in `load_manifest`): a manifest is a JSON list of CaseManifest. Swap that
function when P3-S01's real format lands. Layout: <out_dir>/<run_id>/{meta.json,records/}.
Records hold only AgentRunRecord fields; hidden-test output is never written anywhere here.
"""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from traceforge.contracts.agent_run import AgentRunRecord, Diagnosis
from traceforge.contracts.case_manifest import CaseManifest
from traceforge.evaluation import store
from traceforge.evaluation.conditions import Condition, condition_sha256, load_condition

RunFn = Callable[[CaseManifest, str, int], AgentRunRecord]


class FreezeError(RuntimeError):
    pass


class StopRun(RuntimeError):
    """Raise from run_fn on provider outage: stop cleanly; rerun with the same run_id resumes."""


def load_manifest(path: Path) -> tuple[list[CaseManifest], str]:
    raw = path.read_bytes()
    cases = [CaseManifest.model_validate(c) for c in json.loads(raw)]
    return cases, hashlib.sha256(raw).hexdigest()


def check_freeze(manifest_path: Path, sha: str, split: str) -> None:
    """Test split runs only when the manifest hash equals the frozen `test.sha256` beside it."""
    if split != "test":
        return
    frozen = manifest_path.parent / "test.sha256"
    if not frozen.is_file():
        raise FreezeError("test split refused: no test.sha256 (manifest not frozen)")
    if frozen.read_text("utf-8").split()[0].lower() != sha:
        raise FreezeError("test split refused: manifest hash differs from test.sha256")


def _git_sha() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=10
        )
        return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _crash_record(case: CaseManifest, cond: Condition, rep: int, err: Exception) -> AgentRunRecord:
    return AgentRunRecord(
        run_id="-",
        case_id=case.case_id,
        condition=cond.name,
        model_id=cond.model_id,
        provider=cond.provider,
        prompt_hash=cond.prompt_hash,
        diagnosis=Diagnosis(cause_class="insufficient_evidence", abstained=True),
        attempts=0,
        outcome="UNVERIFIED",
        tokens_in=0,
        tokens_out=0,
        cost_usd=0,
        list_price_usd=0,
        latency_ms=0,
        tool_calls=0,
        invalid_tool_calls=0,
        cache_hits=0,
        dataset_sha256="0" * 64,
        git_sha=case.base_sha,
        replicate=rep,
        temperature=cond.temperature,
        failure_reason=f"pipeline_crash: {type(err).__name__}: {err}"[:500],
    )


def run_experiment(
    manifest_path: Path,
    condition: str,
    run_id: str,
    run_fn: RunFn,
    out_dir: Path,
    replicates: int = 1,
    split: str = "dev",
    limit: int | None = None,
    log: Callable[[str], None] = print,
) -> Path:
    cond = load_condition(condition)
    cases, sha = load_manifest(manifest_path)
    check_freeze(manifest_path, sha, split)
    if "hidden" in {p.lower() for p in out_dir.parts}:
        raise ValueError("out_dir must not be a hidden-test location")
    cases = [c for c in cases if c.split == split][:limit]
    run_dir = out_dir / run_id
    meta_path = run_dir / "meta.json"
    started = _now()
    if meta_path.is_file():  # resume: refuse to mix datasets or conditions
        old = json.loads(meta_path.read_text("utf-8"))
        if (old["dataset_sha256"], old["condition"], old["split"]) != (sha, cond.name, split):
            raise ValueError("run_id exists with a different dataset/condition/split")
        started = old["started_at"]
    meta = {
        "run_id": run_id,
        "split": split,
        "dataset_sha256": sha,
        "condition": cond.name,
        "condition_alias": cond.alias,
        "condition_sha256": condition_sha256(cond),
        "model_id": cond.model_id,
        "provider": cond.provider,
        "temperature": cond.temperature,
        "prompt_hash": cond.prompt_hash,
        "git_sha": _git_sha(),
        "replicates": replicates,
        "n_cases": len(cases),
        "n_expected": len(cases) * replicates,
        "started_at": started,
        "finished_at": None,
        "env": {"python": sys.version.split()[0], "platform": platform.platform()},
    }
    store.write_json(meta_path, json.dumps(meta, indent=2))
    for i, case in enumerate(cases, 1):
        for rep in range(replicates):
            if store.has_record(run_dir, case.case_id, rep):
                continue
            try:
                rec = run_fn(case, cond.name, rep)
            except StopRun:
                log("provider outage: stopping; rerun with the same run_id to resume")
                return run_dir
            except Exception as e:  # a crashing case is recorded and the run continues
                rec = _crash_record(case, cond, rep, e)
            rec = rec.model_copy(update={"run_id": run_id, "dataset_sha256": sha})
            path = store.record_path(run_dir, case.case_id, rep)
            store.write_json(path, rec.model_dump_json(indent=2))
            log(f"[{i}/{len(cases)}] {case.case_id} r{rep} -> {rec.outcome}")
    meta["finished_at"] = _now()
    store.write_json(meta_path, json.dumps(meta, indent=2))
    return run_dir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run one condition over a manifest split.")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--condition", required=True, help="L0|G0|L1|G1 (or alias G0F0...)")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--replicates", type=int, default=1)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", type=Path, default=Path("runs"))
    a = ap.parse_args(argv)
    from traceforge.agent.gateway import GatewayError
    from traceforge.agent.pipeline import run_case, sample_sources

    src = sample_sources()  # TODO(P3-S01): real Sources; repair variant once repair_run is wired

    def run_fn(case, condition, replicate):
        try:
            return run_case(case, condition, src, replicate=replicate)
        except GatewayError as e:
            raise StopRun(str(e)) from e

    args = (a.manifest, a.condition, a.run_id, run_fn, a.out, a.replicates, a.split, a.limit)
    try:
        run_experiment(*args)
    except FreezeError as e:
        print(e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
