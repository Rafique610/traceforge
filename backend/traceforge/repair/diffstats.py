"""Facts about a unified diff: files, added/removed lines and the base-file lines it changes.

Used to record "files and lines changed" for every patch attempt (and, offline, to compare an
attempt with the gold fix). Pure text processing; no repository access.
"""

from __future__ import annotations

import re

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def diff_stats(diff: str) -> dict:
    """{"files": {path: {"added": n, "removed": n, "removed_at": [old line numbers],
    "added_after": [old line number each added line follows]}}, "added": n, "removed": n}."""
    files: dict[str, dict] = {}
    cur: dict | None = None
    old_no = 0
    for ln in diff.splitlines():
        if ln.startswith("+++ "):
            path = ln[4:].strip()
            path = path[2:] if path.startswith("b/") else path
            cur = files.setdefault(
                path, {"added": 0, "removed": 0, "removed_at": [], "added_after": []}
            )
        elif (m := _HUNK.match(ln)) and cur is not None:
            old_no = int(m.group(1)) - 1  # last old line consumed before the hunk
        elif cur is None or ln.startswith(("--- ", "diff ", "\\")):
            continue
        elif ln.startswith("-"):
            old_no += 1
            cur["removed"] += 1
            cur["removed_at"].append(old_no)
        elif ln.startswith("+"):
            cur["added"] += 1
            cur["added_after"].append(old_no)
        else:
            old_no += 1
    return {
        "files": files,
        "added": sum(f["added"] for f in files.values()),
        "removed": sum(f["removed"] for f in files.values()),
    }


def changed_lines(diff: str) -> dict[str, tuple[list[str], list[str]]]:
    """{path: (removed line texts, added line texts)}, whitespace-stripped, in order."""
    out: dict[str, tuple[list[str], list[str]]] = {}
    path = None
    for ln in diff.splitlines():
        if ln.startswith("+++ "):
            path = ln[4:].strip()
            path = path[2:] if path.startswith("b/") else path
            out.setdefault(path, ([], []))
        elif path and ln.startswith("-") and not ln.startswith("--- "):
            out[path][0].append(ln[1:].strip())
        elif path and ln.startswith("+") and not ln.startswith("+++ "):
            out[path][1].append(ln[1:].strip())
    return out
