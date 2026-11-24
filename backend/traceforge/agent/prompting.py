"""Versioned prompt templates, prompt_hash and context rendering within the per-prompt budget."""

import hashlib
from pathlib import Path

from traceforge.contracts.context import ContextBundle
from traceforge.contracts.evidence import EvidenceBundle

DIR = Path(__file__).parent / "prompts"
PIPELINES = {  # pipeline version -> (diagnose prompt, patch prompt)
    "v4": ("diagnose_v1", "patch_v4"),  # formal pipeline (patch_v4); unchanged
    "v5": ("diagnose_v2", "patch_v5"),  # development track: symptom, labelled evidence, validation
}
VERSIONS = PIPELINES["v4"]
# PLACEHOLDER until P0-S06 measures the real per-prompt limit of the pinned model (D20 is
# provisional). Overridable via Settings.agent_context_budget_chars once that setting exists.
DEFAULT_CONTEXT_BUDGET_CHARS = 12_000
EVIDENCE_ITEM_CHARS = 1500
HIDDEN_MARKERS = ("hidden",)


def load(name: str) -> tuple[str, str]:
    system, user = (DIR / f"{name}.md").read_text("utf-8").split("---USER---\n")
    return system.strip(), user


def prompt_hash(pipeline: str = "v4") -> str:
    """SHA-256 of the raw template texts (no case data). `v4` is byte-identical to before."""
    text = "".join((DIR / f"{n}.md").read_text("utf-8") for n in PIPELINES[pipeline])
    return hashlib.sha256(text.encode()).hexdigest()


def render_evidence(evidence: EvidenceBundle) -> str:
    return "\n".join(
        f"[{i.id} {i.kind} {i.service}] {i.content[:EVIDENCE_ITEM_CHARS]}" for i in evidence.items
    )


def rendered_hits(ctx: ContextBundle, budget_chars: int) -> list:
    """The hits that fit the per-prompt budget, in the order they are rendered."""
    out, used = [], 0
    for h in sorted(ctx.hits, key=lambda h: -h.score):
        if any(m in h.path.lower() for m in HIDDEN_MARKERS):
            continue
        block = f"[{h.node_id} {h.path}:{h.start_line}-{h.end_line}]\n{h.excerpt}"
        if used + len(block) > budget_chars:
            continue
        out.append((h, block))
        used += len(block)
    return out


def render_context(ctx: ContextBundle, budget_chars: int) -> str:
    """Highest-scoring hits first, never including hidden-test paths, within the char budget."""
    return "\n\n".join(block for _h, block in rendered_hits(ctx, budget_chars))
