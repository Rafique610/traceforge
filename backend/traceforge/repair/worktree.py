"""Disposable git worktrees at base_sha (subprocess git, no shell)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class WorktreeError(RuntimeError):
    pass


def _git(repo: str | Path, *args: str, stdin: str | None = None) -> str:
    # Bytes in and out: text mode would translate line endings on Windows and break `git apply`.
    p = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=None if stdin is None else stdin.encode("utf-8"),
        capture_output=True,
        timeout=60,
        check=False,
    )
    if p.returncode != 0:
        raise WorktreeError(
            f"git {args[0]} failed: {p.stderr.decode('utf-8', 'replace').strip()[:500]}"
        )
    return p.stdout.decode("utf-8", "replace")


def read_base_file(repo: str | Path, base_sha: str, path: str) -> tuple[str | None, bool]:
    """(text, is_symlink) of `path` at base_sha; text is None if missing or not UTF-8."""
    try:
        mode = _git(repo, "ls-tree", base_sha, "--", path).split(" ", 1)[0]
    except WorktreeError:
        return None, False
    if not mode:
        return None, False
    p = subprocess.run(
        ["git", "-C", str(repo), "show", f"{base_sha}:{path}"], capture_output=True, check=False
    )
    if p.returncode != 0:
        return None, False
    try:
        return p.stdout.decode("utf-8"), mode == "120000"
    except UnicodeDecodeError:
        return None, mode == "120000"


@contextmanager
def worktree(
    repo: str | Path, base_sha: str, diff: str | None = None, root: str | Path | None = None
) -> Iterator[Path]:
    """Create a detached worktree at base_sha, optionally apply `diff`, always clean up."""
    tmp = Path(tempfile.mkdtemp(prefix="tf-wt-", dir=root))
    wt = tmp / "wt"
    try:
        _git(repo, "worktree", "add", "--detach", str(wt), base_sha)
        if diff:
            _git(wt, "apply", "--check", "--whitespace=nowarn", "-", stdin=diff)
            _git(wt, "apply", "--whitespace=nowarn", "-", stdin=diff)
        yield wt
    finally:
        try:
            _git(repo, "worktree", "remove", "--force", str(wt))
        except WorktreeError:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            _git(repo, "worktree", "prune")
        except WorktreeError:
            pass
