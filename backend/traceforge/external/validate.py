"""Red/green validation of BugsInPy cases in our sandbox (P5-S05). Docker only, no model calls.

A case is kept when, twice each, the reproducer fails on the buggy tree (on the bug's own failing
tests) and passes with the real fix, and the hidden suite passes with the fix. The visible suite
is pruned to the test files that are fully green with the fix (so a correct patch can pass it),
then re-checked. Results: `runs/external/bugsinpy/validation.json`; kept cases get an evidence
bundle in `runs/evidence/` so the Investigate path can load them.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from traceforge.contracts.test_run import TestRunRequest, TestRunResult
from traceforge.external import bugsinpy as b
from traceforge.sandbox import make_run_tests

FIX = "fix.patch"
EVIDENCE = b.REPO / "runs" / "evidence"
REPORT = b.WORK / "validation.json"


def _tree(cid: str, project: str, root: Path, fixed: bool) -> Path:
    wt = root / ("fixed" if fixed else "buggy")
    shutil.copytree(b.case_dir(cid) / "src", wt / "lab" / project)
    if fixed:  # own repo first: inside another repo, git apply silently skips "outside" paths
        subprocess.run(["git", "init", "-q", str(wt)], check=True)  # noqa: S603,S607
        p = subprocess.run(  # noqa: S603,S607
            ["git", "apply", "-v", f"--directory=lab/{project}", str(b.case_dir(cid) / FIX)],
            cwd=wt, check=True, capture_output=True, text=True,
        )  # fmt: skip
        if "Applied patch" not in p.stderr:
            raise subprocess.CalledProcessError(1, "git apply", stderr=p.stderr.encode())
    return wt


def _named_failed(res: TestRunResult, names: list[str]) -> bool:
    bad = {t.id.split("::")[-1] for t in res.tests if t.outcome in ("failed", "error")}
    return bool(set(names) & bad)


def _green(res: TestRunResult) -> bool:
    return res.error is None and not res.timed_out and res.failed == 0 and res.passed > 0


def validate_one(project: str, n: int) -> dict:
    cid = b.case_id(project, n)
    m = b.meta(cid)
    case = b.CaseManifest.model_validate(
        next(c for c in json.loads(b.MANIFEST.read_text("utf-8")) if c["case_id"] == cid)
    )
    cfg = b.sandbox_cfg(case)
    names = [t.split("::")[-1] for t in m["failing"]]
    out: dict = {"case_id": cid, "kept": False, "checks": {}}
    with tempfile.TemporaryDirectory(prefix="tf-bip-", dir=b.WORK) as tmp:
        root = Path(tmp)
        run = make_run_tests(root, b.REPO / "datasets" / "hidden_tests",
                             b.REPO / "datasets" / "reproducers", cfg)  # fmt: skip

        def go(wt: Path, suite: str, t: int = 300) -> TestRunResult:
            return run(TestRunRequest(case_id=cid, worktree_path=str(wt), suite=suite, timeout_s=t))

        try:
            buggy, fixed = _tree(cid, project, root, False), _tree(cid, project, root, True)
        except subprocess.CalledProcessError as e:
            out["why"] = f"fix does not apply: {e.stderr.decode()[:200]}"
            return out
        red = [go(buggy, "reproducer") for _ in range(2)]
        out["checks"]["red"] = [_named_failed(r, names) for r in red]
        if not all(out["checks"]["red"]):
            out["why"] = "reproducer does not fail on the buggy tree: " + (
                red[0].error or red[0].stdout_tail[-300:]
            )
            return out
        green = [go(fixed, "reproducer") for _ in range(2)]
        out["checks"]["green"] = [_green(r) for r in green]
        if not all(out["checks"]["green"]):
            out["why"] = "reproducer does not pass with the real fix: " + (
                green[0].error or green[0].stdout_tail[-300:]
            )
            return out
        hidden = go(fixed, "hidden")
        out["checks"]["hidden"] = _green(hidden)
        if not out["checks"]["hidden"]:
            out["why"] = f"hidden suite not green with the fix: {hidden.error}"
            return out
        svc = fixed / "lab" / project
        seen = {f.relative_to(svc).as_posix() for f in (svc / "tests").rglob("test_*.py")}

        def prune(keep: set[str]) -> None:
            for f in (svc / "tests").rglob("test_*.py"):
                if f.relative_to(svc).as_posix() not in keep:
                    f.unlink()

        # pass 1: files that fail to import stop pytest before anything runs, so drop them first
        # (e.g. fastapi's tutorial tests need its docs on the path)
        vis = go(fixed, "visible", 900)
        broken = {t.id for t in vis.tests if t.outcome == "error" and "::" not in t.id}
        prune(seen - broken)
        # pass 2: keep the files whose every test passes with the real fix
        vis = go(fixed, "visible", 900)
        files: dict[str, bool] = {}
        for t in vis.tests:
            f = t.id.split("::")[0]
            files[f] = files.get(f, True) and t.outcome in ("passed", "skipped")
        keep = sorted(f for f, ok in files.items() if ok and f in seen)
        m["visible_files"] = keep
        (b.case_dir(cid) / "case.json").write_text(json.dumps(m, indent=1), "utf-8")
        prune(set(keep))
        vis2 = go(fixed, "visible", 900)
        out["checks"]["visible"] = {"files_kept": len(keep), "files_seen": len(seen),
                                    "green_after_prune": _green(vis2),
                                    "tests": vis2.passed}  # fmt: skip
        if not _green(vis2):
            out["why"] = f"pruned visible suite not green: {vis2.error or vis2.failed}"
            return out
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / f"{cid}.json").write_text(b.empty_bundle(case).model_dump_json(indent=1), "utf-8")
    out["kept"] = True
    return out


def validate_many(project: str, bugs: list[int]) -> None:  # pragma: no cover (Docker)
    rep = json.loads(REPORT.read_text("utf-8")) if REPORT.is_file() else {}
    for n in bugs:
        r = validate_one(project, n)
        rep[r["case_id"]] = r
        REPORT.write_text(json.dumps(rep, indent=1), "utf-8")
        print(
            r["case_id"], "KEPT" if r["kept"] else f"DROPPED: {r.get('why', '')[:300]}", r["checks"]
        )
