"""Experiment runner: one condition over one split, resumable, freeze-guarded.

ASSUMPTION (isolated in `load_manifest`): a manifest is a JSON list of CaseManifest. Swap that
function when P3-S01's real format lands. Layout: <out_dir>/<run_id>/{meta.json,records/}.
Records hold only AgentRunRecord fields; hidden-test output is never written anywhere here.
"""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from traceforge.contracts.agent_run import AgentRunRecord, Diagnosis
from traceforge.contracts.case_manifest import CaseManifest
from traceforge.evaluation import store
from traceforge.evaluation.conditions import Condition, condition_sha256, load_condition
from traceforge.evaluation.errors import StopRun

MAX_WORKERS = 4  # AxForge documents 8 concurrent calls per account; stay at half of that
RunFn = Callable[[CaseManifest, str, int], AgentRunRecord]


class FreezeError(RuntimeError):
    pass


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


def prompting_hash(pipeline: str) -> str:
    from traceforge.agent import prompting

    return prompting.prompt_hash(pipeline)


def _final_refusal(a: argparse.Namespace) -> str | None:
    """Why a --final-rc1 invocation may not start (None = allowed). The final evaluation is the
    only place the frozen test split is used with pipeline v5, and only as frozen and selected."""
    import json as _json

    from traceforge.evaluation.fingerprint import code_fingerprint

    if a.pipeline != "v5" or a.split != "test" or a.diagnose_only:
        return "--final-rc1 needs --pipeline v5 --split test (and not --diagnose-only)"
    if "final" not in {x.lower() for x in a.out.resolve().parts}:
        return "--final-rc1 needs an --out directory under 'final'"
    if (a.provider or "axforge") != "axforge" or (a.model or "glm-5.3-flash") != "glm-5.3-flash":
        return "the final evaluation uses AxForge glm-5.3-flash only"
    if not a.selection or not a.selection.is_file() or not a.rc_fingerprint:
        return "--final-rc1 needs --selection and --rc-fingerprint"
    chosen = {c for g in _json.loads(a.selection.read_text("utf-8"))["cases"] for c in [g]}
    if not a.case_ids or not set(a.case_ids) <= chosen:
        return "--case-ids must be a subset of the frozen selection"
    if a.rc_fingerprint != code_fingerprint()["sha256"]:
        return "the code fingerprint differs from the frozen RC1 fingerprint (the code changed)"
    return None


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
    provider: str | None = None,
    model: str | None = None,
    workers: int = 1,
    case_ids: list[str] | None = None,
    pipeline: str = "v4",
    diagnose_only: bool = False,
    extra_meta: dict | None = None,
    replicate_start: int = 0,
    final_rc1: bool = False,
    axforge_slot: str | None = None,
) -> Path:
    cond = load_condition(condition)
    if (
        provider or model
    ):  # provider/model are a run-level binding; everything else stays as defined
        cond = cond.model_copy(
            update={k: v for k, v in (("provider", provider), ("model_id", model)) if v}
        )
    tier = (
        "final-rc1"
        if final_rc1
        else (
            "official"
            if (cond.provider, cond.model_id) == ("axforge", "glm-5.3-flash") and pipeline == "v4"
            else "development"  # dev-d1 (v5) is never official, whatever the provider
        )
    )
    cases, sha = load_manifest(manifest_path)
    check_freeze(manifest_path, sha, split)
    if "hidden" in {p.lower() for p in out_dir.parts}:
        raise ValueError("out_dir must not be a hidden-test location")
    cases = [c for c in cases if c.split == split]
    if case_ids:  # an explicit selection must exist: a typo must not silently shrink the run
        missing = set(case_ids) - {c.case_id for c in cases}
        if missing:
            raise ValueError(f"case ids not in the {split} split: {sorted(missing)}")
        cases = [c for c in cases if c.case_id in set(case_ids)]
    cases = cases[:limit]
    run_dir = out_dir / run_id
    meta_path = run_dir / "meta.json"
    started = _now()
    if meta_path.is_file():  # resume: refuse to mix datasets or conditions
        old = json.loads(meta_path.read_text("utf-8"))
        if (old["dataset_sha256"], old["condition"], old["split"]) != (sha, cond.name, split):
            raise ValueError("run_id exists with a different dataset/condition/split")
        if (old["provider"], old["model_id"], old.get("pipeline_version", "v4")) != (
            cond.provider,
            cond.model_id,
            pipeline,
        ):  # a resumed evaluation never silently changes provider, model or pipeline
            raise ValueError("run_id exists with a different provider/model/pipeline")
        if old.get("extra") != extra_meta:
            raise ValueError("run_id exists with a different stage/source (extra_meta)")
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
        "tier": tier,  # official = axforge glm-5.3-flash only; development is never official
        "temperature": cond.temperature,
        "prompt_hash": cond.prompt_hash
        if pipeline == "v4"
        else prompting_hash(pipeline),  # v5: the dev-d1 prompts, not the formal ones
        "pipeline_version": pipeline,
        "diagnose_only": diagnose_only,
        "dev_config": "dev-d1" if pipeline == "v5" else None,
        "extra": extra_meta,
        "git_sha": _git_sha(),
        "replicates": replicates,
        "replicate_start": replicate_start,
        "n_cases": len(cases),
        "n_expected": len(cases) * replicates,
        "started_at": started,
        "finished_at": None,
        "env": {"python": sys.version.split()[0], "platform": platform.platform()},
    }
    if axforge_slot:  # the key SLOT NAME only (never a key); absent for single-key runs
        meta["axforge_slot"] = axforge_slot
    store.write_json(meta_path, json.dumps(meta, indent=2))
    reps = range(replicate_start, replicate_start + replicates)  # staged runs: r0, then r1...
    tasks = [(i, c, r) for i, c in enumerate(cases, 1) for r in reps]
    stop = threading.Event()
    lock = threading.Lock()

    def say(msg: str) -> None:
        with lock:
            log(msg)

    def one(task: tuple[int, CaseManifest, int]) -> None:
        i, case, rep = task
        if stop.is_set() or store.has_record(run_dir, case.case_id, rep):
            return
        ready = getattr(run_fn, "ready", None)
        if ready is not None:
            try:
                ready(case)
            except Exception as e:  # not runnable yet: skipped, nothing written, resumable
                say(f"[{i}/{len(cases)}] {case.case_id} skipped: {e}")
                return
        try:
            rec = run_fn(case, cond.name, rep)
        except StopRun:
            stop.set()  # no new case starts; cases already in flight finish and are recorded
            say("provider outage: stopping; rerun with the same run_id to resume")
            return
        except Exception as e:  # a crashing case is recorded and the run continues
            rec = _crash_record(case, cond, rep, e)
        rec = rec.model_copy(update={"run_id": run_id, "dataset_sha256": sha})
        store.write_json(
            store.record_path(run_dir, case.case_id, rep), rec.model_dump_json(indent=2)
        )
        say(f"[{i}/{len(cases)}] {case.case_id} r{rep} -> {rec.outcome}")

    if workers <= 1:
        for t in tasks:
            one(t)
    else:  # independent cases in parallel; every case has its own repo, containers and record file
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(one, tasks))
    if stop.is_set():
        return run_dir
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
    ap.add_argument(
        "--replicate-start",
        type=int,
        default=0,
        help="first replicate index of this invocation (r0, r1, r2 can be run as separate stages)",
    )
    ap.add_argument(
        "--share-diagnosis",
        action="store_true",
        help="with --patch-from: the saved diagnosis may come from the run of the same retrieval "
        "arm with the other feedback setting (L1 uses L0's diagnosis, G1 uses G0's)",
    )
    ap.add_argument(
        "--final-rc1",
        action="store_true",
        help="the final controlled evaluation with release candidate RC1 on the frozen test split: "
        "needs --pipeline v5, --split test, an --out under 'final', --selection and "
        "--rc-fingerprint equal to the current code fingerprint, AxForge only",
    )
    ap.add_argument("--selection", type=Path, help="frozen case selection file (final mode)")
    ap.add_argument("--rc-fingerprint", help="expected code fingerprint sha256 (final mode)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--case-ids", nargs="+", help="run only these case ids (must be in the split)")
    ap.add_argument("--out", type=Path, default=Path("runs"))
    ap.add_argument("--provider", help="run-level provider override (default: from the condition)")
    ap.add_argument("--model", help="run-level model override (default: from the condition)")
    ap.add_argument(
        "--real", action="store_true", help="real sources: committed cases, saved evidence"
    )
    ap.add_argument("--evidence-dir", type=Path, default=Path("../runs/evidence"))
    ap.add_argument(
        "--pipeline",
        choices=["v4", "v5"],
        default="v4",
        help="v4 = formal pipeline (default, unchanged); v5 = development track (always the "
        "development tier, use a development run id)",
    )
    ap.add_argument(
        "--patch-from",
        type=Path,
        help="dev-d1 patch stage: use the saved diagnoses (and evidence) of this completed "
        "diagnosis run directory; nothing is re-diagnosed. Needs --pipeline v5",
    )
    ap.add_argument(
        "--frozen-manifest",
        type=Path,
        help="hash manifest the saved diagnosis files must match before they are used",
    )
    ap.add_argument(
        "--diagnose-only",
        action="store_true",
        help="v5 only: stop after the diagnosis (no patch is requested)",
    )
    ap.add_argument(
        "--axforge-billing-verified",
        action="store_true",
        help="REQUIRED for any AxForge run: you confirmed on the AxForge dashboard that only free "
        "allowance is used and auto top-up is off",
    )
    ap.add_argument(
        "--axforge-key",
        choices=["1", "2"],
        help="which AxForge key slot this process uses (default: setting, normally 1); "
        "2 is refused unless the owner enabled it",
    )
    ap.add_argument(
        "--workers", type=int, default=1, help=f"parallel cases (max {MAX_WORKERS}; beatapi: 1)"
    )
    a = ap.parse_args(argv)
    from traceforge.agent.gateway import GatewayError
    from traceforge.agent.pipeline import run_case, sample_sources

    if a.final_rc1:
        bad = _final_refusal(a)
        if bad:
            print(f"refused: {bad}", file=sys.stderr)
            return 2
    elif a.pipeline == "v5" and (
        a.split != "dev" or "development" not in {x.lower() for x in a.out.resolve().parts}
    ):
        print(  # dev-d1 can never write into the formal results or touch the frozen test split
            "refused: --pipeline v5 (dev-d1) needs --split dev and an --out under 'development'",
            file=sys.stderr,
        )
        return 2
    if a.patch_from and (a.pipeline != "v5" or a.diagnose_only):
        print("refused: --patch-from needs --pipeline v5 and not --diagnose-only", file=sys.stderr)
        return 2
    if a.patch_from and not a.patch_from.is_dir():
        print(f"refused: {a.patch_from} is not a completed diagnosis run", file=sys.stderr)
        return 2
    if a.diagnose_only and a.pipeline != "v5":
        print("refused: --diagnose-only is a dev-d1 option (--pipeline v5)", file=sys.stderr)
        return 2
    cond = load_condition(a.condition)
    provider, model = a.provider or cond.provider, a.model or cond.model_id
    if provider == "axforge":  # includes the default: conditions are bound to AxForge
        from traceforge.agent import axforge

        if not a.axforge_billing_verified:
            print(axforge.NOT_AUTHORIZED, file=sys.stderr)
            return 4
        from traceforge.config import get_settings

        if a.axforge_key:
            os.environ["TRACEFORGE_AXFORGE_KEY_SLOT"] = a.axforge_key
            get_settings.cache_clear()
        slot = get_settings().axforge_key_slot
        try:
            axforge.authorize(a.run_id, slot=slot)  # also refuses if the usage ledger is missing
        except axforge.AxForgeRefused as e:
            print(e, file=sys.stderr)
            return 5
        print(
            f"WARNING: AxForge run {a.run_id}: billing confirmed by owner; internal ceiling "
            f"{axforge.SAFETY_CEILING:,} tokens still applies",
            flush=True,
        )
    workers = max(1, a.workers)
    slot = "1"
    if provider == "axforge":
        slot = get_settings().axforge_key_slot
    if provider == "beatapi" and workers > 1:
        print("beatapi allows one successful request per minute: using 1 worker", file=sys.stderr)
        workers = 1
    if provider == "axforge" and workers > 1:
        # measured 23 Nov 2026: 4 concurrent requests -> 3 x 429; 2 workers -> a 429 while a sibling
        # request was in flight. This key behaves as one request at a time, whatever the docs say.
        print("axforge answered 429 to concurrent requests: using 1 worker", file=sys.stderr)
        workers = 1
    workers = min(workers, MAX_WORKERS)
    if a.real:
        from traceforge.evaluation.real_run import make_real_run_fn
        from traceforge.faultgen.validate import SANDBOX_CFGS
        from traceforge.sandbox.images import ensure_image

        for cfg in SANDBOX_CFGS.values():  # build/reuse the images once, before parallel workers
            ensure_image(cfg)

        run_fn = make_real_run_fn(
            a.manifest,
            a.evidence_dir,
            a.out / a.run_id,
            provider,
            model,
            pipeline=a.pipeline,
            diagnose_only=a.diagnose_only,
            patch_from=a.patch_from,
            frozen=a.frozen_manifest,
            share_diagnosis=a.share_diagnosis,
            final_rc1=a.final_rc1,
        )
    else:
        src = sample_sources()  # sample cases only: for runner development, never for research

        def run_fn(case, condition, replicate):
            try:
                return run_case(case, condition, src, replicate=replicate)
            except GatewayError as e:
                raise StopRun(str(e)) from e

    args = (a.manifest, a.condition, a.run_id, run_fn, a.out, a.replicates, a.split, a.limit)
    import contextlib

    from traceforge.agent import beatapi

    guard = (  # one BeatAPI run at a time, machine-wide; a second launch is refused up front
        beatapi.single_instance(label=f"run_id={a.run_id}")
        if provider == "beatapi"
        else contextlib.nullcontext()
    )
    try:
        with guard:
            print(f"pid={os.getpid()} run_id={a.run_id} provider={provider}", flush=True)
            run_experiment(
                *args,
                provider=a.provider,
                model=a.model,
                workers=workers,
                case_ids=a.case_ids,
                pipeline=a.pipeline,
                diagnose_only=a.diagnose_only,
                extra_meta=(
                    {"patch_from": a.patch_from.name, "share_diagnosis": a.share_diagnosis}
                    if a.patch_from
                    else None
                ),
                replicate_start=a.replicate_start,
                final_rc1=a.final_rc1,
                axforge_slot=slot if provider == "axforge" else None,
            )
    except beatapi.BeatApiBusy as e:
        print(e, file=sys.stderr)
        return 3
    except FreezeError as e:
        print(e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
