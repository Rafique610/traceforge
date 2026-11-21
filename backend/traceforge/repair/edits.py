"""Search/replace edit blocks: parse, apply (exact, unambiguous only), convert to unified diff."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass


class EditError(ValueError):
    """An edit block is invalid; `reason` is a stable machine-readable code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


@dataclass(frozen=True)
class EditBlock:
    path: str
    old: str
    new: str


_BLOCK = re.compile(
    r"<<<<<<< SEARCH[ \t]+(?P<path>\S+)[ \t]*\n(?P<old>.*?)\n?=======\n"
    r"(?P<new>.*?)\n?>>>>>>> REPLACE",
    re.DOTALL,
)


def parse_blocks(text: str) -> list[EditBlock]:
    """Parse `<<<<<<< SEARCH path / old / ======= / new / >>>>>>> REPLACE` blocks."""
    blocks = [EditBlock(m["path"], m["old"], m["new"]) for m in _BLOCK.finditer(text)]
    if not blocks:
        raise EditError("malformed_edit", "no SEARCH/REPLACE block found")
    if any(not b.old.strip() for b in blocks):
        raise EditError("malformed_edit", "empty SEARCH text")
    return blocks


def apply_edits(files: dict[str, str], blocks: list[EditBlock]) -> dict[str, str]:
    """Return new contents of every edited file. Old text must match exactly once."""
    out = dict(files)
    for b in blocks:
        if b.path not in out:
            raise EditError("file_missing", b.path)
        count = out[b.path].count(b.old)
        if count == 0:
            raise EditError("no_match", b.path)
        if count > 1:
            raise EditError("ambiguous_match", b.path)
        out[b.path] = out[b.path].replace(b.old, b.new, 1)
    return {p: out[p] for p in {b.path for b in blocks}}


def to_unified_diff(old: dict[str, str], new: dict[str, str]) -> str:
    """Deterministic git-apply compatible diff (a/ b/ prefixes) for the changed files."""
    parts: list[str] = []
    for path in sorted(new):
        a = old[path].splitlines(keepends=True)
        b = new[path].splitlines(keepends=True)
        if a == b:
            continue
        body = list(difflib.unified_diff(a, b, f"a/{path}", f"b/{path}", n=3))
        fixed = [
            ln if ln.endswith("\n") else ln + "\n\\ No newline at end of file\n" for ln in body
        ]
        parts.append(f"diff --git a/{path} b/{path}\n" + "".join(fixed))
    return "".join(parts)
