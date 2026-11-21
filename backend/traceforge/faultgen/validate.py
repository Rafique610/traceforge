# ruff: noqa: E501
"""Validate cases with the REAL sandbox: `python -m traceforge.faultgen.validate [--case ID ...]`.

Per case (D27): reproducer + visible + hidden on the ORIGINAL tree and on the BROKEN tree, each run 3 times;
any change of outcome between runs = flaky = rejected. Repairable classes: original green; broken
reproducer and hidden red; applying the gold fix (reverse of mutation.patch) turns them green again.
runtime_dependency / insufficient_evidence: the tree is not mutated, so original == broken; the
reproducer demonstrates the symptom surface and must pass consistently; runtime cases also get a live
stop-the-container check. Also: schema, base_sha drift, leakage scan, hidden-vs-visible input overlap (D31).
"""

import argparse
import json
import shutil
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from traceforge.contracts.case_manifest import REPAIRABLE, CaseManifest
from traceforge.contracts.test_run import TestRunRequest, TestRunResult
from traceforge.faultgen import lab_tree
from traceforge.faultgen.generate import materialize
from traceforge.faultgen.leakage import gold_terms, scan_visible, shared_inputs
from traceforge.faultgen.patching import PatchError, apply_patch
from traceforge.sandbox import make_run_tests
from traceforge.sandbox.config import SandboxConfig

RunFn = Callable[[TestRunRequest], TestRunResult]
LAB_REQS = (
    "pytest==8.3.4 fastapi==0.165.0 sqlalchemy==2.1.9 pydantic-settings==2.16.3 "
    "redis==8.1.0 httpx==0.28.1"
)
SANDBOX_CFG = SandboxConfig(requirements=LAB_REQS, workdir_rel="lab/shop_api")
RUNS = 3


@dataclass
class LoadedCase:
    manifest: CaseManifest
    patch: str
    meta: dict
    datasets: Path

    @property
    def repairable(self) -> bool:
        return self.manifest.cause_class in REPAIRABLE


@dataclass
class CaseReport:
    case_id: str
    cause_class: str
    fault_family: str
    distance: int | None
    checks: dict[str, str] = field(default_factory=dict)  # name -> "ok" | detail
    problems: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.problems


def load_cases(datasets: Path, manifest: str = "dev.json") -> list[LoadedCase]:
    rows = json.loads((datasets / "manifests" / manifest).read_text("utf-8"))
    out = []
    for row in rows:
        m = CaseManifest.model_validate(row)
        cdir = datasets / "cases" / m.case_id
        patch_file = cdir / "mutation.patch"
        patch = patch_file.read_text("utf-8") if patch_file.is_file() else ""
        out.append(
            LoadedCase(m, patch, json.loads((cdir / "meta.json").read_text("utf-8")), datasets)
        )
    return out


def _obs(r: TestRunResult) -> tuple:
    return (
        r.passed,
        r.failed,
        bool(r.timed_out),
        r.error,
        tuple(sorted((t.id, t.outcome) for t in r.tests)),
    )


def _green(o: tuple) -> bool:
    return o[0] > 0 and o[1] == 0 and not o[2] and o[3] is None


def _red(o: tuple) -> bool:
    return o[1] > 0 and not o[2]


def _files(path: Path) -> dict[str, str]:
    return (
        {p.name: p.read_text("utf-8") for p in sorted(path.glob("*.py"))} if path.is_dir() else {}
    )


def default_runner_factory(datasets: Path) -> Callable[[Path], RunFn]:
    def factory(tree: Path) -> RunFn:
        return make_run_tests(
            tree,
            hidden_dir=datasets / "hidden_tests",
            reproducer_dir=datasets / "reproducers",
            cfg=SANDBOX_CFG,
        )

    return factory


def _static_checks(case: LoadedCase, rep: CaseReport, lab: Path) -> None:
    m = case.manifest
    sha = lab_tree.base_sha(lab)
    rep.checks["base_sha"] = "ok" if sha == m.base_sha else "drift"
    if sha != m.base_sha:
        rep.problems.append(
            f"base_sha drift: manifest {m.base_sha[:12]} != lab {sha[:12]} (regenerate)"
        )
    repro = _files(case.datasets / "reproducers" / m.case_id)
    hidden = _files(case.datasets / "hidden_tests" / m.case_id)
    if case.repairable and not hidden:
        rep.problems.append("repairable case has no hidden tests on disk")
    edited: dict[str, str] = {}
    if case.patch:
        scratch = Path(tempfile.mkdtemp(prefix="tf-leak-"))
        try:
            materialize(case.patch, scratch, lab)
            edited = {s.path: lab_tree.read_lf(scratch / s.path) for s in m.gold_symbols}
        except (PatchError, OSError) as e:
            rep.problems.append(f"mutation.patch does not apply: {e}")
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
    try:
        leaks = scan_visible(
            repro,
            gold_terms(m, edited, case.meta.get("runtime", {}))
            - set(case.meta.get("allowed_terms", {})),
        )
    except LookupError as e:
        leaks = [f"cannot scan: {e}"]
    rep.checks["leakage"] = "ok" if not leaks else "; ".join(leaks)
    rep.problems += [f"leakage: {x}" for x in leaks]
    allowed = case.meta.get("allowed_shared", {})
    shared = [x for x in (shared_inputs(repro, hidden) if hidden else []) if x not in allowed]
    rep.checks["hidden_inputs_differ"] = "ok" if not shared else f"shared {shared}"
    if shared:
        rep.problems.append(f"hidden tests share input literals with visible tests: {shared}")


def _stable(rep: CaseReport, label: str, run: RunFn, tree: Path, cid: str, suite: str) -> tuple:
    req = TestRunRequest(case_id=cid, worktree_path=str(tree), suite=suite)  # type: ignore[arg-type]
    seen = [_obs(run(req)) for _ in range(RUNS)]
    flaky = len(set(seen)) != 1
    if flaky:
        rep.problems.append(f"flaky: {label}/{suite} outcomes differ across {RUNS} runs")
    rep.checks[f"{label}_{suite}"] = (
        "FLAKY"
        if flaky
        else f"{'green' if _green(seen[0]) else 'red'} x{RUNS} stable "
        f"({seen[0][0]} passed, {seen[0][1]} failed)"
    )
    return seen[0]


def validate_case(
    case: LoadedCase,
    runner_factory: Callable[[Path], RunFn] | None = None,
    lab: Path | None = None,
    work_root: Path | None = None,
    live: bool = True,
) -> CaseReport:
    m = case.manifest
    lab = lab or lab_tree.repo_root() / "lab"
    rep = CaseReport(m.case_id, m.cause_class, m.fault_family, m.distance)
    _static_checks(case, rep, lab)
    factory = runner_factory or default_runner_factory(case.datasets)
    work = Path(tempfile.mkdtemp(prefix="tf-faultgen-", dir=work_root))
    try:
        orig = materialize("", work / "orig", lab)
        run_o = factory(orig)
        suites = ["reproducer", "visible"] + (["hidden"] if case.repairable else [])
        for s in suites:
            ob = _stable(rep, "original", run_o, orig, m.case_id, s)
            if not _green(ob):
                rep.problems.append(
                    f"original tree: {s} suite not green ({ob[0]} passed, {ob[1]} failed, error={ob[3]})"
                )
        if not case.repairable:
            rep.checks["broken_tree"] = (
                "identical to original (nothing mutated); reproducer shows the symptom"
            )
            _runtime_live(case, rep, lab, live)
            return rep
        broken = materialize(case.patch, work / "broken", lab)
        run_b = factory(broken)
        b = {s: _stable(rep, "broken", run_b, broken, m.case_id, s) for s in suites}
        if not _red(b["reproducer"]):
            rep.problems.append(
                "fault not reproduced: reproducer is not red on the broken tree "
                f"({b['reproducer'][0]} passed, {b['reproducer'][1]} failed, error={b['reproducer'][3]})"
            )
        if not _red(b["hidden"]):
            rep.problems.append("hidden suite is not red on the broken tree")
        rep.checks["broken_visible_note"] = (
            "visible suite red"
            if _red(b["visible"])
            else "visible suite green (fault not caught by visible tests)"
        )
        gold = materialize(case.patch, work / "gold", lab)
        apply_patch(gold, case.patch, reverse=True)
        run_g = factory(gold)
        for s in suites:
            req = TestRunRequest(case_id=m.case_id, worktree_path=str(gold), suite=s)  # type: ignore[arg-type]
            g = _obs(run_g(req))
            rep.checks[f"gold_fix_{s}"] = "green" if _green(g) else "NOT GREEN"
            if not _green(g):
                rep.problems.append(
                    f"gold fix: {s} suite not green ({g[0]} passed, {g[1]} failed, error={g[3]})"
                )
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return rep


def _runtime_live(case: LoadedCase, rep: CaseReport, lab: Path, live: bool) -> None:
    stop = case.meta.get("runtime", {}).get("stop")
    if not stop:
        return
    if not live:
        rep.checks["live_runtime"] = "skipped (--no-live)"
        return
    from traceforge.faultgen.live import live_runtime_check

    issues = live_runtime_check(list(stop), lab)
    rep.checks["live_runtime"] = "ok" if not issues else "; ".join(issues)
    rep.problems += [f"live runtime: {i}" for i in issues]


def format_table(reports: list[CaseReport]) -> str:
    rows = [("case", "class", "family", "distance", "result")]
    for r in reports:
        rows.append(
            (
                r.case_id,
                r.cause_class,
                r.fault_family,
                str(r.distance),
                "PASS" if r.passed else "FAIL",
            )
        )
    widths = [max(len(row[i]) for row in rows) for i in range(5)]
    return "\n".join(
        "  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)) for row in rows
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="traceforge.faultgen.validate")
    ap.add_argument("--datasets", type=Path, default=lab_tree.datasets_dir())
    ap.add_argument("--manifest", default="dev.json")
    ap.add_argument("--case", action="append")
    ap.add_argument("--no-live", action="store_true")
    ap.add_argument("--work-dir", type=Path, default=None)
    ap.add_argument("--json", type=Path, help="write the full report here")
    args = ap.parse_args(argv)
    cases = [
        c
        for c in load_cases(args.datasets, args.manifest)
        if not args.case or c.manifest.case_id in args.case
    ]
    reports = [validate_case(c, work_root=args.work_dir, live=not args.no_live) for c in cases]
    print(format_table(reports))
    for r in reports:
        print(f"\n{r.case_id}:")
        for k, v in r.checks.items():
            print(f"  {k}: {v}")
        for p in r.problems:
            print(f"  PROBLEM: {p}")
    if args.json:
        args.json.write_text(
            json.dumps([r.__dict__ | {"passed": r.passed} for r in reports], indent=2), "utf-8"
        )
    return 0 if all(r.passed for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
