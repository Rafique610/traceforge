"""Agent tools over a disposable worktree + the edit policy. Same tools for every task."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import sandbox_exec
import worktree

READ_ROOTS = ("backend/traceforge", "backend/tests")
WRITE_ROOTS = READ_ROOTS
MAX_READ_LINES = 250
MAX_READ_CHARS = 14000
MAX_GREP_MATCHES = 60
MAX_RUN_TESTS = 12
TEXT_SUFFIXES = {".py", ".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".ini", ".sql", ""}


class ToolError(Exception):
    """Reported back to the model as an error result (counted in tool-call stats)."""


def _fn(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required}}}


S = {"type": "string"}
I = {"type": "integer"}  # noqa: E741
SCHEMAS = [
    _fn("list_dir", "List a directory (path relative to the repo root, e.g. 'backend/traceforge').",
        {"path": S}, ["path"]),
    _fn("read_file", f"Read a file with line numbers (max {MAX_READ_LINES} lines per call).",
        {"path": S, "start": I, "end": I}, ["path"]),
    _fn("grep", "Regex search (python re) in files under a path; returns file:line:text.",
        {"pattern": S, "path": S}, ["pattern", "path"]),
    _fn("apply_edit", "Replace SEARCH with REPLACE in a file; SEARCH must occur exactly once. "
        "To create a NEW file under backend/tests/ pass search='' and the file content as replace.",
        {"path": S, "search": S, "replace": S}, ["path", "search", "replace"]),
    _fn("run_tests", "Run pytest in an isolated sandbox on your current working copy. "
        "paths: e.g. ['tests/reports'] or ['tests/agent/test_gateway.py'] (relative to backend/).",
        {"paths": {"type": "array", "items": S}}, ["paths"]),
    _fn("submit_final", "Finish. Call exactly once when done.",
        {"diagnosis": S, "root_cause_file": S, "summary": S},
        ["diagnosis", "root_cause_file", "summary"]),
]


def norm_rel(path: str) -> str:
    p = str(path).strip().replace("\\", "/")
    if re.match(r"^[A-Za-z]:", p) or p.startswith("/"):
        raise ToolError("absolute paths are not allowed; use a path relative to the repo root")
    parts = [x for x in p.split("/") if x not in ("", ".")]
    if ".." in parts:
        raise ToolError("'..' is not allowed")
    return "/".join(parts)


def _under(rel: str, roots: tuple[str, ...]) -> bool:
    return any(rel == r or rel.startswith(r + "/") for r in roots)


class Toolbox:
    def __init__(self, root: Path, hidden_names: set[str] | None = None,
                 sandbox: Callable[..., dict] | None = None):
        self.root = root.resolve()
        self.hidden = hidden_names or set()  # basenames / rel paths no tool may touch or create
        self.sandbox = sandbox or sandbox_exec.run_pytest
        self.edits: list[dict] = []
        self.test_runs: list[dict] = []
        self.files_modified: set[str] = set()
        self.files_created: set[str] = set()

    # --- path policy -------------------------------------------------------------------
    def _resolve(self, path: str, roots: tuple[str, ...], allow_root_listing: bool = False) -> tuple[str, Path]:
        rel = norm_rel(path)
        parts = rel.split("/")
        if ".git" in parts or "docs" in parts:
            raise ToolError("path not allowed")
        if rel in self.hidden or parts[-1] in self.hidden or "test_zz_hidden" in parts[-1]:
            raise ToolError("path not allowed")
        if not (_under(rel, roots) or (allow_root_listing and rel in ("", "backend"))):
            raise ToolError(f"path must be under {' or '.join(roots)}")
        full = (self.root / rel).resolve()
        if not full.is_relative_to(self.root) or any(
            p.is_symlink() for p in [full, *full.parents] if p.is_relative_to(self.root)
        ):
            raise ToolError("path escapes the working copy")
        return rel, full

    # --- tools -------------------------------------------------------------------------
    def list_dir(self, path: str = ".") -> str:
        rel, full = self._resolve(path, READ_ROOTS, allow_root_listing=True)
        if not full.is_dir():
            raise ToolError("not a directory")
        if rel == "":
            return "backend/"
        if rel == "backend":
            return "traceforge/\ntests/"
        names = sorted(p.name + ("/" if p.is_dir() else "") for p in full.iterdir()
                       if p.name != "__pycache__" and "test_zz_hidden" not in p.name)
        return "\n".join(names[:200]) or "(empty)"

    def read_file(self, path: str, start: int = 1, end: int | None = None) -> str:
        rel, full = self._resolve(path, READ_ROOTS)
        if not full.is_file():
            raise ToolError("not a file")
        lines = worktree.read_text(full)[0].split("\n")
        start = max(1, int(start or 1))
        end = min(int(end or start + MAX_READ_LINES - 1), start + MAX_READ_LINES - 1, len(lines))
        out = "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1))
        note = "" if end >= len(lines) else f"\n[file has {len(lines)} lines; showing {start}-{end}]"
        if len(out) > MAX_READ_CHARS:
            out, note = out[:MAX_READ_CHARS], "\n[truncated: too many characters; narrow the range]"
        return out + note

    def grep(self, pattern: str, path: str) -> str:
        rel, base = self._resolve(path, READ_ROOTS)
        try:
            rx = re.compile(pattern)
        except re.error as e:
            raise ToolError(f"bad regex: {e}") from e
        files = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file())
        hits: list[str] = []
        for f in files:
            if f.suffix not in TEXT_SUFFIXES or "__pycache__" in f.parts or "test_zz_hidden" in f.name:
                continue
            frel = f.relative_to(self.root).as_posix()
            try:
                text = worktree.read_text(f)[0]
            except (UnicodeDecodeError, OSError):
                continue
            for n, line in enumerate(text.split("\n"), 1):
                if rx.search(line):
                    hits.append(f"{frel}:{n}:{line[:200]}")
                    if len(hits) >= MAX_GREP_MATCHES:
                        return "\n".join(hits) + f"\n[stopped at {MAX_GREP_MATCHES} matches]"
        return "\n".join(hits) or "(no matches)"

    def apply_edit(self, path: str, search: str, replace: str) -> str:
        rel, full = self._resolve(path, WRITE_ROOTS)
        if not isinstance(search, str) or not isinstance(replace, str):
            raise ToolError("search and replace must be strings")
        if search == "":  # create a NEW test file
            if not rel.startswith("backend/tests/") or not rel.endswith(".py"):
                raise ToolError("new files may only be created as .py under backend/tests/")
            if full.exists():
                raise ToolError("file already exists; give a non-empty search to edit it")
            full.parent.mkdir(parents=True, exist_ok=True)
            worktree.write_text(full, replace, "\n")
            self.files_created.add(rel)
            self.edits.append({"path": rel, "kind": "create", "chars": len(replace)})
            return f"created {rel} ({len(replace)} chars)"
        if not full.is_file():
            raise ToolError("file does not exist")
        text, eol = worktree.read_text(full)
        n = text.count(search.replace("\r\n", "\n"))
        if n != 1:
            raise ToolError(f"SEARCH must match exactly once; it matched {n} times")
        worktree.write_text(full, text.replace(search.replace("\r\n", "\n"), replace), eol)
        self.files_modified.add(rel)
        self.edits.append({"path": rel, "kind": "edit", "chars": len(replace)})
        return f"edited {rel}"

    def run_tests(self, paths: list[str]) -> str:
        if not isinstance(paths, list) or not paths:
            raise ToolError("paths must be a non-empty list like ['tests/reports']")
        if len(self.test_runs) >= MAX_RUN_TESTS:
            raise ToolError(f"run_tests limit reached ({MAX_RUN_TESTS} per task)")
        for p in paths:
            try:
                sandbox_exec.normalise_test_path(str(p))
            except ValueError as e:
                raise ToolError(str(e)) from e
            if "test_zz_hidden" in str(p):
                raise ToolError("path not allowed")
        r = self.sandbox(self.root, [str(p) for p in paths])
        self.test_runs.append({"paths": paths, "passed": r["passed"], "failed": r["failed"],
                               "error": r["error"], "edits_before": len(self.edits)})
        return sandbox_exec.summarise(r)

    def dispatch(self, name: str, raw_args: str) -> tuple[str, str]:
        """(category, text) where category is ok | tool_error | unknown_tool | bad_args."""
        fns = {"list_dir": self.list_dir, "read_file": self.read_file, "grep": self.grep,
               "apply_edit": self.apply_edit, "run_tests": self.run_tests}
        if name not in fns:
            return "unknown_tool", f"ERROR: unknown tool '{name}'"
        try:
            args = json.loads(raw_args) if raw_args and raw_args.strip() else {}
            if not isinstance(args, dict):
                raise ValueError("arguments must be a JSON object")
        except ValueError as e:
            return "bad_args", f"ERROR: malformed arguments: {e}"
        try:
            return "ok", fns[name](**args)
        except TypeError as e:
            return "bad_args", f"ERROR: bad arguments: {str(e)[:200]}"
        except ToolError as e:
            return "tool_error", f"ERROR: {e}"
        except Exception as e:  # never crash the run on a tool bug
            return "tool_error", f"ERROR: {type(e).__name__}: {str(e)[:200]}"
