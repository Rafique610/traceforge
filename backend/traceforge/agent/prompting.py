"""Versioned prompt templates, prompt_hash and context rendering within the per-prompt budget."""

import hashlib
from pathlib import Path

from traceforge.contracts.context import ContextBundle
from traceforge.contracts.evidence import EvidenceBundle

DIR = Path(__file__).parent / "prompts"
VERSIONS = ("diagnose_v1", "patch_v2")
# PLACEHOLDER until P0-S06 measures the real per-prompt limit of the pinned model (D20 is
# provisional). Overridable via Settings.agent_context_budget_chars once that setting exists.
DEFAULT_CONTEXT_BUDGET_CHARS = 12_000
EVIDENCE_ITEM_CHARS = 1500
HIDDEN_MARKERS = ("hidden",)


def load(name: str) -> tuple[str, str]:
    system, user = (DIR / f"{name}.md").read_text("utf-8").split("---USER---\n")
    return system.strip(), user


def prompt_hash() -> str:
    """SHA-256 of the raw template texts (no case data)."""
    text = "".join((DIR / f"{n}.md").read_text("utf-8") for n in VERSIONS)
    return hashlib.sha256(text.encode()).hexdigest()


def render_evidence(evidence: EvidenceBundle) -> str:
    return "\n".join(
        f"[{i.id} {i.kind} {i.service}] {i.content[:EVIDENCE_ITEM_CHARS]}" for i in evidence.items
    )


def render_context(ctx: ContextBundle, budget_chars: int) -> str:
    """Highest-scoring hits first, never including hidden-test paths, within the char budget."""
    out, used = [], 0
    for h in sorted(ctx.hits, key=lambda h: -h.score):
        if any(m in h.path.lower() for m in HIDDEN_MARKERS):
            continue
        block = f"[{h.node_id} {h.path}:{h.start_line}-{h.end_line}]\n{h.excerpt}"
        if used + len(block) > budget_chars:
            continue
        out.append(block)
        used += len(block)
    return "\n\n".join(out)
