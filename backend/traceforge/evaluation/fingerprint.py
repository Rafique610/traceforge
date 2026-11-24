"""Code fingerprint for run metadata: which behaviour-affecting source a run was produced with.

`git_sha` alone cannot say this (the working tree is uncommitted during development), so reuse
audits had to reason about what changed. A run records the sha256 of the files that determine its
prompts, tools, retrieval and validation; two runs with the same fingerprint, evidence, symptom and
settings ran the same pipeline. The fingerprint covers v5 (dev-d1) behaviour files only.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
FILES = (
    "agent/diagnose.py", "agent/tools.py", "agent/patch.py", "agent/pipeline.py",
    "agent/symptom.py", "agent/evidence_view.py", "agent/prompting.py", "agent/handoff.py",
    "agent/prompts/diagnose_v2.md", "agent/prompts/patch_v5.md",
    "retrieval/anchors.py", "retrieval/retrieve.py", "retrieval/graph_ranker.py",
    "retrieval/routes.py", "retrieval/lexical.py", "retrieval/corpus.py",
    "retrieval/context_budget.py", "retrieval/sources.py",
    "repair/scope.py", "repair/policy.py", "repair/loop.py",
    "diagnostics/__init__.py",
    "diagnostics/rules.py",
    "repair/feedback.py",
    "agent/real_sources.py",
    "agent/repair_run.py",
    "evidence/collector.py",
    "evidence/logs.py",
)  # fmt: skip


def code_fingerprint(files: tuple[str, ...] = FILES, root: Path = PKG) -> dict:
    """{"sha256": combined, "files": {relpath: sha256}} (CRLF/LF-insensitive)."""
    parts: dict[str, str] = {}
    for rel in files:
        data = (root / rel).read_bytes().replace(b"\r\n", b"\n")
        parts[rel] = hashlib.sha256(data).hexdigest()
    combined = hashlib.sha256("".join(f"{k}:{v}\n" for k, v in sorted(parts.items())).encode())
    return {"sha256": combined.hexdigest(), "files": parts}
