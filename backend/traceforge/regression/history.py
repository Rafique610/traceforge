"""Append-only, human-readable patch version history (one JSON object per line)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

Outcome = str  # targeted_failed | visible_failed | visible_passed | sandbox_error


@dataclass
class PatchVersion:
    attempt: int
    patch_sha256: str
    impact_sha256: str | None
    selected_tests: list[str]
    targeted_result: dict[str, Any] | None  # {"passed","failed","failing":[ids]} or None
    full_visible_result: dict[str, Any] | None
    outcome: Outcome
    selection_fallback: str | None = None
    note: str | None = None
    event: str = field(default="patch_version")


class PatchHistory:
    """In-memory list plus optional JSONL file (opened for append only; never rewritten)."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.versions: list[PatchVersion] = []
        self.events: list[dict[str, Any]] = []

    def _write(self, obj: dict[str, Any]) -> None:
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(obj, sort_keys=True) + "\n")

    def append(self, v: PatchVersion) -> None:
        self.versions.append(v)
        self._write(asdict(v))

    def append_event(self, event: str, **data: Any) -> None:
        """Non-version records (e.g. the hidden gate ran once: counts only, never content)."""
        rec = {"event": event, **data}
        self.events.append(rec)
        self._write(rec)

    @staticmethod
    def read(path: str | Path) -> list[dict[str, Any]]:
        return [json.loads(x) for x in Path(path).read_text("utf-8").splitlines() if x.strip()]
