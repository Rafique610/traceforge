# ruff: noqa: E501
"""Real end-to-end run of one case: real evidence, retrieval, model, sandbox, incident DB.

    python -m traceforge.agent.e2e --case shop_api-001 --condition G1 --provider ollama \
        --model qwen2.5-coder-7b-ctx16k [--replicate 0] [--label EXPERIMENTAL]

Runs `run_case_with_repair` on a disposable git repo built from the case's faulty tree (generator
patch applied to the pristine lab, committed in a scratch dir). The patch only ever exists in a
disposable worktree and as text in `runs/e2e/<run_id>/patch.diff` and the incident DB: this CLI
never writes to lab/ or datasets/ (human approval stays mandatory). Hidden tests are mounted by the
sandbox only; every prompt is checked against their names/paths. Output (one run, one record):
`runs/e2e/<run_id>/{meta.json,records/<case>.r<k>.json,patch.diff,diagnosis.json,trace.json,
incident.json}` (the layout `evaluation.analysis.report --runs-dir runs/e2e` reads).
"""

import argparse
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from traceforge.agent import gateway
from traceforge.agent.lab_collect import SCRATCH
from traceforge.agent.persist import RunLog, save_outcome
from traceforge.agent.real_sources import (
    HiddenLeakGuard,
    make_sandbox_run_tests,
    real_sources,
)
from traceforge.agent.repair_run import run_case_with_repair
from traceforge.agent.rc2.version import rc2_fingerprint, run_label, select_chat_fn
from traceforge.agent.symptoms import symptom_for
from traceforge.config import Settings
from traceforge.contracts.case_manifest import REPAIRABLE, CaseManifest
from traceforge.contracts.evidence import EvidenceBundle
from traceforge.evaluation.fingerprint import code_fingerprint
from traceforge.faultgen.generate import materialize

REPO = Path(__file__).resolve().parents[3]
RC2_FP_FILE = REPO / "results/rc2/rc2-fingerprint.txt"


def rm_tree(path: Path) -> None:
    """rmtree that also removes read-only git objects (Windows)."""
    import os
    import stat

    def onexc(fn, p, _exc):  # noqa: ANN001
        os.chmod(p, stat.S_IWRITE)
        fn(p)

    shutil.rmtree(path, ignore_errors=False, onexc=onexc) if path.exists() else None


def _git(repo: Path, *args: str) -> str:
    p = subprocess.run(  # noqa: S603
        ["git", "-C", str(repo), "-c", "user.name=tf", "-c", "user.email=tf@example.org", *args],  # noqa: S607
        capture_output=True, text=True, timeout=120, check=True,
    )  # fmt: skip
    return p.stdout.strip()


def build_repo(case: CaseManifest, datasets: Path, dest: Path) -> tuple[Path, str]:
    """Faulty tree as a git repo (the repair loop works on worktrees of its HEAD)."""
    patch = (datasets / "cases" / case.case_id / "mutation.patch").read_text("utf-8")
    materialize(patch, dest)
    subprocess.run(["git", "init", "-q", "-b", "main", str(dest)], check=True)  # noqa: S603,S607
    _git(dest, "config", "core.autocrlf", "false")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-q", "-m", "faulty tree")
    return dest, _git(dest, "rev-parse", "HEAD")


def allowlist(repo: Path, service: str) -> list[str]:
    out = []
    for p in sorted((repo / "lab" / service).rglob("*")):
        rel = p.relative_to(repo).as_posix()
        if p.is_file() and p.suffix in (".py", ".toml", ".ini", ".yaml") and "/tests/" not in rel:
            out.append(rel)
    return out


def visible_sources(repo: Path, datasets: Path, case: CaseManifest) -> list[str]:
    files = [*(repo / "lab" / case.service / "tests").glob("*.py")]
    files += (datasets / "reproducers" / case.case_id).glob("*.py")
    return [f.read_text("utf-8") for f in files]


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-")


def _rc_label(rc: str) -> dict:
    """Version + matching fingerprint for meta.json; refuses a label/fingerprint mismatch."""
    if rc == "rc2":
        sha = rc2_fingerprint()["sha256"]
        recorded = RC2_FP_FILE.read_text("utf-8").strip() if RC2_FP_FILE.is_file() else None
        if recorded != sha:  # rc2 files changed since the recorded fingerprint: refresh it
            RC2_FP_FILE.parent.mkdir(parents=True, exist_ok=True)
            RC2_FP_FILE.write_text(sha, "utf-8")
    else:
        sha = code_fingerprint()["sha256"]
    return run_label(rc, sha)  # rc1 must equal the frozen RC1 fingerprint, rc2 must differ


def _saved_evidence(evidence_dir: Path, case_id: str):  # noqa: ANN202
    p = Path(evidence_dir) / f"{case_id}.json"
    return EvidenceBundle.model_validate_json(p.read_text("utf-8")) if p.is_file() else None


def run(a: argparse.Namespace) -> dict:
    from sqlalchemy.orm import Session

    datasets = a.manifest.parents[1]
    settings = Settings(llm_provider=a.provider, llm_model=a.model)
    run_id = a.run_id or f"e2e-{a.case}-{a.condition}-{slug(a.model)}-r{a.replicate}"
    if a.provider == "axforge":  # the billing gate applies here exactly as in the experiment runner
        from traceforge.agent import axforge

        if not a.axforge_billing_verified:
            raise SystemExit(axforge.NOT_AUTHORIZED)
        axforge.authorize(run_id)
    out = a.out / run_id
    shutil.rmtree(out, ignore_errors=True)
    repo_dir = SCRATCH / "repos" / run_id
    rm_tree(repo_dir)
    from traceforge.agent.real_sources import ManifestCaseSource

    case = ManifestCaseSource(a.manifest).get(a.case)
    repo, head = build_repo(case, datasets, repo_dir)
    src = real_sources(a.manifest, a.evidence_dir, repo)
    guard = HiddenLeakGuard(
        datasets / "hidden_tests",
        [case.case_id],
        [repo / "lab" / case.service / "tests", datasets / "reproducers" / case.case_id],
    )
    v5 = a.pipeline == "v5"
    rc = getattr(a, "rc", "rc1")
    rc_label = _rc_label(rc)  # raises VersionLabelError on a label/fingerprint mismatch
    rc2_log: list[dict] = []
    ev = _saved_evidence(a.evidence_dir, case.case_id) if rc == "rc2" else None
    chat = select_chat_fn(  # rc1: identity; rc2: wraps the guarded gateway (guard still sees every request)
        rc,
        guard.wrap(
            partial(
                gateway.chat, settings=settings, replicate_index=a.replicate, seed=0,
                temperature=0.0, use_cache=not v5,  # v5: every request is live (no stale replays)
            )
        ),
        rc2_log,
        ev,
    )  # fmt: skip
    runlog = RunLog(make_sandbox_run_tests(repo, datasets, case.service))
    sym_obj = None
    if v5:  # the symptom comes from the visible tests run on the base commit (no gold terms)
        from traceforge.agent import symptom as symptom_mod
        from traceforge.repair.worktree import worktree

        with worktree(str(repo), head) as wt:
            sym_obj = symptom_mod.collect_symptom(runlog, str(wt), case.case_id)
        if (why := symptom_mod.validate(sym_obj, guard.check)) and sym_obj.status == "ok":
            sym_obj.status = f"blocked: {why[0]}"  # fail closed: nothing enters a prompt
    artifacts: dict = {}
    db: Session | None = None
    inc = None
    if not a.no_db:
        from traceforge.database import SessionLocal
        from traceforge.incidents import service
        from traceforge.incidents.schemas import IncidentCreate

        db = SessionLocal()
        incident_symptom = (
            ("\n".join(sym_obj.texts()) or "No failing visible test on the base commit.")[:10_000]
            if v5
            else symptom_for(case, datasets)
        )
        inc = service.create_incident(
            db, IncidentCreate(case_id=case.case_id, service=case.service, symptom=incident_symptom)
        )  # fmt: skip
    t0 = datetime.now(UTC)
    rec = run_case_with_repair(
        inc or case, a.condition, src,
        repo_path=str(repo), base_sha=head, run_tests=runlog,
        allowlist=allowlist(repo, case.service),
        visible_test_sources=visible_sources(repo, datasets, case),
        db=db, settings=settings, chat_fn=chat, replicate=a.replicate,
        dataset_sha256=src.cases.sha256, artifacts=artifacts,
        pipeline=a.pipeline, symptom=sym_obj,
    )  # fmt: skip
    rr = artifacts.get("repair")
    if db is not None and inc is not None:
        save_outcome(db, inc, cause_class=rec.diagnosis.cause_class, base_sha=case.base_sha,
                     rr=rr, runlog=runlog, graph=src.context.graph if case.cause_class in REPAIRABLE else None)  # fmt: skip
        db.refresh(inc)
    out.mkdir(parents=True, exist_ok=True)
    (out / "records").mkdir()
    (out / "records" / f"{case.case_id}.r{a.replicate}.json").write_text(
        rec.model_dump_json(indent=2), "utf-8"
    )
    (out / "meta.json").write_text(json.dumps({
        "run_id": run_id, "label": a.label, "n_expected": 1, "started_at": t0.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(), "provider": a.provider, "model": a.model,
        "dataset_sha256": rec.dataset_sha256, "repair_repo_head": head, "hidden_guard_calls": guard.calls,
        "hidden_markers_checked": len(guard.markers), "hidden_fragment_hits": len(guard.fragment_hits),
        "incident_id": str(inc.id) if inc else None,
        "rc_version": rc, **rc_label,
    }, indent=2), "utf-8")  # fmt: skip
    (out / "rc2_log.json").write_text(json.dumps(rc2_log, indent=2), "utf-8")
    if sym_obj is not None:
        (out / "symptom.json").write_text(json.dumps(sym_obj.as_dict(), indent=2), "utf-8")
    diff = artifacts.get("diff")
    (out / "patch.diff").write_text(diff or "", "utf-8")
    sub = artifacts.get("submitted")
    (out / "diagnosis.json").write_text(sub.model_dump_json(indent=2) if sub else "null", "utf-8")
    (out / "trace.json").write_text(json.dumps(artifacts.get("trace"), indent=2), "utf-8")
    (out / "repair.json").write_text(json.dumps({
        "outcome": rr.outcome if rr else None, "reason": rr.reason if rr else None,
        "attempts": [{"n": x.n, "reasons": x.reasons, "visible_passed": x.visible_passed,
                      "has_diff": x.diff is not None} for x in rr.attempts] if rr else [],
        "hidden_passed": rr.hidden_passed if rr else None,
        "hidden_tests": [t.model_dump() for t in rr.hidden_result.tests] if rr and rr.hidden_result else [],
        "signature_changed": rr.signature_changed if rr else None,
    }, indent=2), "utf-8")  # fmt: skip
    if inc is not None:
        from traceforge.incidents import repository

        ev = [(e.from_state, e.to_state, e.actor) for e in repository.list_events(db, inc.id)]
        (out / "incident.json").write_text(json.dumps({
            "incident_id": str(inc.id), "state": str(inc.state), "cause_class": inc.cause_class,
            "transitions": [f"{f}->{t} ({x})" for f, t, x in ev],
        }, indent=2), "utf-8")  # fmt: skip
    if db is not None:
        db.close()
    return {"run_id": run_id, "out": str(out), "incident_id": str(inc.id) if inc else None,
            "record": json.loads(rec.model_dump_json())}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--case", required=True)
    ap.add_argument("--condition", required=True, choices=["L0", "G0", "L1", "G1"])
    ap.add_argument("--provider", default="ollama")
    ap.add_argument("--model", default="qwen2.5-coder-7b-ctx16k")
    ap.add_argument("--replicate", type=int, default=0)
    ap.add_argument("--label", default="")
    ap.add_argument("--rc", choices=["rc1", "rc2"], default="rc1", help="pipeline version (default rc1, unchanged)")
    ap.add_argument("--run-id")
    ap.add_argument("--manifest", type=Path, default=REPO / "datasets/manifests/dev.json")
    ap.add_argument("--evidence-dir", type=Path, default=REPO / "runs/evidence")
    ap.add_argument("--out", type=Path, default=REPO / "runs/e2e")
    ap.add_argument("--no-db", action="store_true", help="do not persist to the incident DB")
    ap.add_argument(
        "--pipeline",
        choices=["v4", "v5"],
        default="v5",
        help="v5 (default): symptom from the visible tests, labelled evidence, validated "
        "diagnosis, scoped patches; v4: the formal pipeline",
    )
    ap.add_argument(
        "--axforge-billing-verified",
        action="store_true",
        help="REQUIRED for AxForge: the owner confirmed the free allowance only (see the runner)",
    )
    a = ap.parse_args(argv)
    if a.provider == "beatapi":  # same one-run-at-a-time lock the experiment runner takes
        from traceforge.agent import beatapi

        with beatapi.single_instance(label=f"e2e case={a.case} rc={a.rc}"):
            res = run(a)
    else:
        res = run(a)
    r = res["record"]
    keys = (
        "outcome",
        "hidden_passed",
        "attempts",
        "tokens_in",
        "tokens_out",
        "latency_ms",
        "failure_reason",
    )
    print(json.dumps({"run_id": res["run_id"], "incident_id": res["incident_id"],
                      "diagnosis": r["diagnosis"], **{k: r[k] for k in keys}}, indent=1))  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
