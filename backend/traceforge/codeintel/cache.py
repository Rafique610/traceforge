"""Disk cache of per-file facts, keyed by base_sha, validated by per-file content hash.

The assembled graph is always rebuilt from facts (cheap); only changed files are re-parsed.
When no cache exists for this base_sha, facts from the most recent cache of the same repo path
are reused for files whose hash still matches (incremental across SHAs).
"""

import hashlib
import json
from pathlib import Path

VERSION = 3  # bump when the facts schema changes


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FactsCache:
    def __init__(self, cache_dir: Path, repo: Path, base_sha: str):
        self.dir = cache_dir
        self.repo_key = hashlib.sha1(str(repo.resolve()).encode()).hexdigest()[:10]
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in base_sha)
        self.path = cache_dir / f"{safe}__{self.repo_key}.json"
        self.entries: dict[str, dict] = {}
        self._load()

    def _read(self, p: Path) -> dict[str, dict]:
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            return doc["files"] if doc.get("version") == VERSION else {}
        except (OSError, ValueError, KeyError):
            return {}

    def _load(self) -> None:
        self.entries = self._read(self.path)
        if not self.entries and self.dir.exists():
            others = sorted(
                self.dir.glob(f"*__{self.repo_key}.json"), key=lambda p: p.stat().st_mtime
            )
            if others:
                self.entries = self._read(others[-1])

    def get(self, rel: str, digest: str) -> dict | None:
        e = self.entries.get(rel)
        return e["facts"] if e and e["sha"] == digest else None

    def save(self, files: dict[str, dict]) -> None:
        """files: rel -> {"sha", "facts"}; drops entries for deleted files."""
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": VERSION, "files": files}, sort_keys=True))
        tmp.replace(self.path)
