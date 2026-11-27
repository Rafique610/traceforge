"""BugsInPy cases (P5-S05): real bugs from real projects' git history, in the lab layout.

    python -m traceforge.external.bugsinpy prepare fastapi 2 4 5   # fetch, build case files
    python -m traceforge.external.bugsinpy validate fastapi 2 4 5  # red/green twice, prune tests

A case's project tree (the buggy commit) is placed at `lab/<project>/` of the scratch repo, so the
frozen RC1 pipeline, which only reads and edits `lab/<service>/`, runs on it unchanged. The
project's own test file from the fix commit is both the reproducer and the hidden suite; the
visible suite is the buggy commit's tests that pass once the real fix is applied.

BugsInPy metadata has no licence, so nothing of it is committed: it is fetched at run time into
`runs/external/bugsinpy/` (git-ignored), and so are the derived test dirs below `datasets/`.
"""

import argparse
import ast
import io
import json
import re
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

from traceforge.contracts.case_manifest import CaseManifest, GoldSymbol
from traceforge.contracts.evidence import EvidenceBundle
from traceforge.sandbox.config import SandboxConfig

REPO = Path(__file__).resolve().parents[3]
WORK = REPO / "runs" / "external" / "bugsinpy"
MANIFEST = REPO / "datasets" / "manifests" / "bugsinpy.json"
RAW = "https://raw.githubusercontent.com/soarsmu/BugsInPy/master/projects/{p}/bugs/{n}/{f}"
GITHUB = {"fastapi": "https://github.com/tiangolo/fastapi"}
PYTEST = "pytest==8.3.4"  # our runner's pytest flags need a modern pytest
# dev tooling and pytest's own pinned deps (they clash with PYTEST); the project itself comes from
# the case tree, never from PyPI
DROP = {
    "fastapi", "pytest", "pytest-cov", "coverage", "pluggy", "py", "atomicwrites", "packaging",
    "more-itertools", "importlib-metadata", "zipp", "black", "flake8", "mypy", "mypy-extensions",
    "isort", "autoflake", "pyflakes", "pycodestyle", "mccabe", "typed-ast", "pathspec", "appdirs",
    "toml", "pytoml", "regex", "mkdocs", "mkdocs-material", "mkdocs-material-extensions",
    "markdown", "markdown-include", "pymdown-extensions", "pygments", "lunr", "nltk", "joblib",
    "livereload", "tornado", "docutils", "flit", "flit-core", "typer-cli", "shellingham", "tqdm",
}  # fmt: skip
HIDDEN = "test_hidden_behaviour.py"
DEF = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def case_id(project: str, n: int) -> str:
    return f"bugsinpy-{project}-{n}"


def parse_info(text: str) -> dict[str, str]:
    return dict(re.findall(r'(\w+)="([^"]*)"', text))


def failing_tests(run_test_sh: str) -> list[str]:
    """Test node ids from `run_test.sh` (`pytest path::name` lines)."""
    return [
        t for ln in run_test_sh.splitlines() if ln.startswith("pytest ") for t in ln.split()[1:]
    ]


def requirements(text: str) -> str:
    keep = []
    for ln in text.lstrip("﻿").splitlines():
        name = re.split(r"[=<>!~ ]", ln.strip(), maxsplit=1)[0]
        if name and not name.startswith("#") and name.lower().replace("_", "-") not in DROP:
            keep.append(ln.strip())
    return " ".join(sorted({*keep, PYTEST}, key=str.lower))


def changed_lines(patch: str) -> dict[str, set[int]]:
    """Old-side (buggy) line numbers each file's fix touches. A pure insertion counts the line
    before it, so the symbol it lands in is found."""
    out: dict[str, set[int]] = {}
    path, old = None, 0
    for ln in patch.splitlines():
        if ln.startswith("--- "):
            path = ln[4:].removeprefix("a/").strip()
        elif ln.startswith("+++ "):
            continue
        elif m := re.match(r"@@ -(\d+)", ln):
            old = int(m.group(1))
        elif path and ln.startswith("-"):
            out.setdefault(path, set()).add(old)
            old += 1
        elif path and ln.startswith("+"):
            out.setdefault(path, set()).add(max(old - 1, 1))
        elif path and ln.startswith(" "):
            old += 1
    return out


def _defs(tree: ast.AST) -> list[tuple[int, int, str]]:
    found: list[tuple[int, int, str]] = []

    def walk(node: ast.AST, prefix: str) -> None:
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, DEF):
                q = f"{prefix}{ch.name}"
                found.append((ch.lineno, ch.end_lineno or ch.lineno, q))
                walk(ch, q + ".")
            else:
                walk(ch, prefix)

    walk(tree, "")
    return found


def gold_symbols(src: Path, patch: str, project: str) -> list[GoldSymbol]:
    """Innermost function/method/class of the buggy tree around every line the real fix touches."""
    out: dict[str, GoldSymbol] = {}
    for path, lines in sorted(changed_lines(patch).items()):
        defs = _defs(ast.parse((src / path).read_text("utf-8")))
        for line in sorted(lines):
            hits = [d for d in defs if d[0] <= line <= d[1]]
            if hits:
                s, e, q = min(hits, key=lambda d: d[1] - d[0])
                out[f"{path}:{q}"] = GoldSymbol(
                    path=f"lab/{project}/{path}", qualname=q, start_line=s, end_line=e
                )
    return list(out.values())


def fetch(project: str, n: int, name: str) -> str:
    cache = WORK / "meta" / case_id(project, n) / name
    if not cache.is_file():
        url = RAW.format(p=project, n=n, f=name)
        with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 (fixed https host)
            raw = r.read()  # some BugsInPy files are UTF-16 with a BOM
            data = raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(data, "utf-8")
    return cache.read_text("utf-8")


def _git(repo: Path, *args: str, binary: bool = False) -> str | bytes:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)  # noqa: S603,S607
    return p.stdout if binary else lf(p.stdout.decode("utf-8"))


def lf(text: str) -> str:
    """Some projects committed CRLF files; the pipeline's edits match text exactly and the model
    copies LF text, so case trees, tests and fixes are all LF (line endings change no behaviour)."""
    return text.replace("\r\n", "\n")


def clone(project: str) -> Path:
    dest = WORK / "repos" / project
    if not (dest / ".git").is_dir():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "-q", "--filter=blob:none", GITHUB[project], str(dest)], check=True
        )  # noqa: S603,S607
    return dest


def _export(repo: Path, sha: str, dest: Path) -> None:
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    tar = _git(repo, "-c", "core.autocrlf=false", "archive", sha, binary=True)
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(dest, filter="data")
    for f in dest.rglob("*"):
        if f.is_file() and b"\r\n" in (data := f.read_bytes()) and b"\0" not in data:
            f.write_bytes(data.replace(b"\r\n", b"\n"))


def case_dir(cid: str) -> Path:
    return WORK / cid


def prepare(project: str, n: int, datasets: Path = REPO / "datasets") -> CaseManifest:
    """Buggy tree, reproducer/hidden tests and the manifest entry for one bug."""
    cid = case_id(project, n)
    info = parse_info(fetch(project, n, "bug.info"))
    patch = fetch(project, n, "bug_patch.txt")
    failing = failing_tests(fetch(project, n, "run_test.sh"))
    repo = clone(project)
    src = case_dir(cid) / "src"
    _export(repo, info["buggy_commit_id"], src)
    test_file = info["test_file"].split(";")[0]
    fixed_test = _git(repo, "show", f"{info['fixed_commit_id']}:{test_file}")
    for sub, name in (
        ("reproducers", "test_symptom.py"),
        ("hidden_tests", "test_hidden_behaviour.py"),
    ):
        d = datasets / sub / cid
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        (d / name).write_text(fixed_test, "utf-8", newline="\n")
    names = [t.split("::")[-1] for t in failing]
    py = ".".join(info["python_version"].split(".")[:2])
    meta = {"python": py, "requirements": requirements(fetch(project, n, "requirements.txt")),
            "buggy": info["buggy_commit_id"], "fixed": info["fixed_commit_id"],
            "test_file": test_file, "failing": failing, "visible_files": None}  # fmt: skip
    (case_dir(cid) / "case.json").write_text(json.dumps(meta, indent=1), "utf-8")
    (case_dir(cid) / "fix.patch").write_text(patch, "utf-8", newline="\n")
    return CaseManifest(
        case_id=cid, split="test", cause_class="application_code", fault_family="bugsinpy",
        service=project, base_sha=info["buggy_commit_id"],
        gold_symbols=gold_symbols(src, patch, project),
        distance=0,  # not computed for external cases; results are never split by it
        reproducer_id=f"datasets/reproducers/{cid}/test_symptom.py::{names[0]}",
        hidden_test_ids=[f"datasets/hidden_tests/{cid}/{HIDDEN}::{x}" for x in names],
        variant_group=f"bugsinpy:{project}-{n}", origin="bugsinpy", log_format="none",
    )  # fmt: skip


def meta(cid: str) -> dict:
    return json.loads((case_dir(cid) / "case.json").read_text("utf-8"))


def sandbox_cfg(case: CaseManifest) -> SandboxConfig:
    m = meta(case.case_id)
    return SandboxConfig(
        requirements=m["requirements"], base_image=f"python:{m['python']}-slim",
        workdir_rel=f"lab/{case.service}", memory="1g", pids_limit=256,
    )  # fmt: skip


def materialize_case(case: CaseManifest, dest: Path) -> None:
    """Buggy tree at `dest/lab/<project>/` with only the validated visible tests, and the case's
    sandbox settings registered for its service (runs are one at a time)."""
    from traceforge.faultgen.validate import SANDBOX_CFGS

    m = meta(case.case_id)
    target = dest / "lab" / case.service
    shutil.copytree(case_dir(case.case_id) / "src", target)
    keep = set(m["visible_files"] or [])
    for f in (target / "tests").rglob("test_*.py"):
        if f.relative_to(target).as_posix() not in keep:
            f.unlink()
    SANDBOX_CFGS[case.service] = sandbox_cfg(case)


def empty_bundle(case: CaseManifest) -> EvidenceBundle:
    """No Docker runtime evidence exists for these bugs; the symptom run supplies the traceback."""
    import hashlib

    return EvidenceBundle(
        incident_id="pending", base_sha=case.base_sha,
        compose_sha256=hashlib.sha256(b"").hexdigest(), items=[],
    )  # fmt: skip


def write_manifest(cases: list[CaseManifest], path: Path = MANIFEST) -> None:
    old = {c["case_id"]: c for c in json.loads(path.read_text("utf-8"))} if path.is_file() else {}
    old |= {c.case_id: c.model_dump(mode="json") for c in cases}
    path.write_text(
        json.dumps(sorted(old.values(), key=lambda c: c["case_id"]), indent=1) + "\n", "utf-8"
    )


def main(argv: list[str] | None = None) -> None:  # pragma: no cover (network + Docker)
    ap = argparse.ArgumentParser(prog="python -m traceforge.external.bugsinpy")
    ap.add_argument("action", choices=["prepare", "validate"])
    ap.add_argument("project", choices=sorted(GITHUB))
    ap.add_argument("bugs", type=int, nargs="+")
    a = ap.parse_args(argv)
    if a.action == "prepare":
        cases = [prepare(a.project, n) for n in a.bugs]
        write_manifest(cases)
        for c in cases:
            print(c.case_id, [f"{g.path}:{g.qualname}" for g in c.gold_symbols])
    else:
        from traceforge.external.validate import validate_many

        validate_many(a.project, a.bugs)


if __name__ == "__main__":  # pragma: no cover
    main()
