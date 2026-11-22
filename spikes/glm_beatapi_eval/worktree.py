"""Disposable git worktrees: create at HEAD, inject the historical bug, strip anything that
reveals the fix, hand the model only backend/traceforge and backend/tests, then remove."""

from __future__ import annotations

import ast
import shutil
import stat
import subprocess
from pathlib import Path

REPO = Path("D:/TraceForge/repo")
EVAL_ROOT = Path("D:/AI/tmp/eval_wt")
SCORE_ROOT = Path("D:/AI/tmp/eval_score")
KEEP_IN_BACKEND = {"traceforge", "tests", "pyproject.toml"}


class WorktreeError(RuntimeError):
    pass


def _git(*args: str, cwd: Path = REPO) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise WorktreeError(f"git {' '.join(args[:2])} failed: {p.stderr.strip()[:300]}")
    return p.stdout


def _rmtree(path: Path) -> None:
    def onerr(fn, p, _):
        Path(p).chmod(stat.S_IWRITE)
        fn(p)

    shutil.rmtree(path, onerror=onerr)


def create(name: str) -> Path:
    path = EVAL_ROOT / name
    if path.exists():
        cleanup(path)
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    _git("worktree", "add", "--detach", str(path), "HEAD")
    return path


def strip(path: Path) -> None:
    """Remove docs/runs/spikes/.memory, the .git file, and every non-source backend entry."""
    for entry in list(path.iterdir()):
        if entry.name != "backend":
            _rmtree(entry) if entry.is_dir() else entry.unlink()
    for entry in list((path / "backend").iterdir()):
        if entry.name not in KEEP_IN_BACKEND:
            _rmtree(entry) if entry.is_dir() else entry.unlink()
    assert not (path / ".git").exists()


def cleanup(path: Path) -> None:
    """Always leave no worktree behind (force-remove, prune, delete any residue)."""
    try:
        _git("worktree", "remove", "--force", str(path))
    except WorktreeError:
        pass
    if path.exists():
        _rmtree(path)
    _git("worktree", "prune")


def read_text(path: Path) -> tuple[str, str]:
    raw = path.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n"), eol


def write_text(path: Path, text: str, eol: str) -> None:
    path.write_bytes(text.replace("\n", eol).encode("utf-8"))


def apply_injections(tree: Path, injections: list[dict]) -> None:
    for inj in injections:
        f = tree / inj["file"]
        text, eol = read_text(f)
        if text.count(inj["old"]) != 1:
            raise WorktreeError(f"injection does not match exactly once in {inj['file']}")
        write_text(f, text.replace(inj["old"], inj["new"]), eol)


def _test_spans(src: str) -> dict[str, tuple[int, int]]:
    spans = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            spans[node.name] = (start, node.end_lineno)
    return spans


def remove_tests(src: str, names: list[str]) -> str:
    spans = _test_spans(src)
    missing = [n for n in names if n not in spans]
    if missing:
        raise WorktreeError(f"tests not found: {missing}")
    lines = src.split("\n")
    for n in sorted(names, key=lambda n: -spans[n][0]):
        a, b = spans[n]
        del lines[a - 1 : b]
    return "\n".join(lines).rstrip("\n") + "\n"


def keep_only_tests(src: str, names: list[str]) -> str:
    """The original file with every test function deleted except `names` (imports kept)."""
    drop = [n for n in _test_spans(src) if n not in names]
    return remove_tests(src, drop) if drop else src


def hidden_files(task: dict, fixed_tree: Path) -> dict[str, str]:
    """{relative path: content} of the scorer-only test files (never placed in the model tree)."""
    out = {}
    for h in task.get("hidden", []):
        src, _ = read_text(fixed_tree / h["file"])
        p = Path(h["file"])
        out[(p.parent / "test_zz_hidden.py").as_posix()] = keep_only_tests(src, h["names"])
    out.update(task.get("hidden_extra_files", {}))
    return out


def build_visible(task: dict, name: str, *, buggy: bool) -> tuple[Path, dict[str, str]]:
    """Create the worktree. Returns (path, hidden files). buggy=False gives the fixed reference.
    The hidden files are extracted from the pristine tree BEFORE the target tests are removed."""
    tree = create(name)
    try:
        hidden = hidden_files(task, tree)
        for h in task.get("hidden", []):
            f = tree / h["file"]
            text, eol = read_text(f)
            write_text(f, remove_tests(text, h["names"]), eol)
        if buggy:
            apply_injections(tree, task["injections"])
        strip(tree)
    except Exception:
        cleanup(tree)
        raise
    return tree, hidden


def scorer_copy(tree: Path, hidden: dict[str, str], name: str) -> Path:
    """A throwaway copy of the (possibly model-edited) tree plus the scorer-only tests."""
    dst = SCORE_ROOT / name
    if dst.exists():
        _rmtree(dst)
    shutil.copytree(tree, dst, ignore=shutil.ignore_patterns("__pycache__"))
    for rel, content in hidden.items():
        (dst / rel).write_text(content, encoding="utf-8")
    return dst


def remove_scorer(dst: Path) -> None:
    if dst.exists():
        _rmtree(dst)


def list_worktrees() -> list[str]:
    return [ln for ln in _git("worktree", "list", "--porcelain").splitlines()
            if ln.startswith("worktree ") and "eval_wt" in ln]
