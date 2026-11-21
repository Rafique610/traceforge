# ruff: noqa: E501
"""Build and apply strict unified diffs (difflib). No external patch tool; context must match exactly."""

import difflib
import re
from pathlib import Path

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class PatchError(RuntimeError):
    pass


def make_patch(edits: dict[str, tuple[str, str]]) -> str:
    """edits: repo-relative path -> (old_text, new_text). Empty string when nothing changes."""
    parts = []
    for path, (old, new) in sorted(edits.items()):
        diff = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=3,
        )
        parts.append("".join(diff))
    return "".join(parts)


def _sections(patch: str) -> list[tuple[str, list[str]]]:
    files: list[tuple[str, list[str]]] = []
    for line in patch.splitlines(keepends=True):
        if line.startswith("--- a/"):
            files.append((line[6:].rstrip("\n"), []))
        elif line.startswith("+++ b/"):
            continue
        elif files:
            files[-1][1].append(line)
    return files


def _apply_one(text: str, lines: list[str], reverse: bool, path: str) -> str:
    src = text.splitlines(keepends=True)
    out: list[str] = []
    pos = 0
    i = 0
    while i < len(lines):
        m = _HUNK.match(lines[i])
        if not m:
            raise PatchError(f"{path}: bad hunk header {lines[i]!r}")
        start = int(m.group(3 if reverse else 1))
        start = start - 1 if int(m.group(4 if reverse else 2) or 1) else start
        out.extend(src[pos:start])
        pos = start
        i += 1
        while i < len(lines) and not lines[i].startswith("@@"):
            tag, body = lines[i][0], lines[i][1:]
            i += 1
            if tag == "\\":
                continue
            removes = tag == ("+" if reverse else "-")
            adds = tag == ("-" if reverse else "+")
            if tag == " " or removes:
                if pos >= len(src) or src[pos] != body:
                    raise PatchError(f"{path}: context mismatch at line {pos + 1} (tree drifted?)")
                pos += 1
                if tag == " ":
                    out.append(body)
            elif adds:
                out.append(body)
    out.extend(src[pos:])
    return "".join(out)


def apply_patch(root: Path, patch: str, reverse: bool = False) -> list[str]:
    """Apply (or reverse-apply) `patch` under `root`; returns touched paths. Raises PatchError."""
    touched = []
    for path, lines in _sections(patch):
        target = root / path
        if not target.is_file():
            raise PatchError(f"{path}: file not found")
        new = _apply_one(
            target.read_bytes().decode("utf-8").replace("\r\n", "\n"), lines, reverse, path
        )
        target.write_bytes(new.encode("utf-8"))
        touched.append(path)
    return touched
