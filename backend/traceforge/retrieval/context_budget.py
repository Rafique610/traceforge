"""Pack ranked chunks into a token budget (largest-score-first = rank order) with line-numbered
excerpts, reasons and de-duplicated overlapping spans.

Token estimate: chars/4 (`codeintel.approx_tokens`), the same approximation as the limits report;
it is NOT a real tokenizer. A hit costs its excerpt plus its id/path/reasons header, because the
agent sees both. About `reserve_fraction` (20%) of the budget is left for the agent's own
`read_symbol` calls, so `tokens_used <= token_budget * (1 - reserve_fraction) <= token_budget`.
"""

from dataclasses import dataclass, field

from traceforge.codeintel import approx_tokens
from traceforge.contracts.context import ContextHit
from traceforge.retrieval.corpus import Chunk

RESERVE_FRACTION = 0.2
MAX_EXCERPT_LINES = 80


@dataclass
class Ranked:
    chunk: Chunk
    score: float
    reasons: list[str]
    forced: bool = False
    forced_rank: int = 0
    hit_id: str = ""  # id reported in the ContextHit (defaults to chunk.hit_id)
    extra: dict = field(default_factory=dict)


def _header_tokens(c: Chunk, reasons: list[str]) -> int:
    return approx_tokens(f"{c.hit_id} {c.path}:{c.start}-{c.end} " + " ".join(reasons))


def _excerpt(
    c: Chunk, emitted: set[tuple[str, int]], room_chars: int | None
) -> tuple[str, int, int]:
    """Numbered excerpt of lines not already emitted for this file; (text, start, end)."""
    new = [(n, t) for n, t in c.lines[:MAX_EXCERPT_LINES] if (c.path, n) not in emitted]
    if c.kind == "config_key":
        new = list(c.lines)
    out, used, kept = [], 0, []
    for n, t in new:
        row = f"{n}: {t}"
        if room_chars is not None and used + len(row) + 1 > room_chars and kept:
            out.append("...")
            break
        out.append(row)
        kept.append(n)
        used += len(row) + 1
    if c.kind == "config_key":
        out += c.notes
    if not kept and c.kind != "config_key":
        return f"(lines {c.start}-{c.end} already shown above)", c.start, c.end
    s, e = (kept[0], kept[-1]) if kept else (c.start, c.end)
    return "\n".join(out), s, e


def pack(ranked: list[Ranked], token_budget: int, reserve: float = RESERVE_FRACTION):
    """-> (hits, tokens_used). Never exceeds `token_budget` (nor the unreserved 80% of it)."""
    usable = int(token_budget * (1 - reserve))
    used, hits = 0, []
    emitted: set[tuple[str, int]] = set()
    for r in ranked:
        c = r.chunk
        room = usable - used - _header_tokens(c, r.reasons)
        if room <= 0:
            continue
        text, s, e = _excerpt(c, emitted, None)
        cost = _header_tokens(c, r.reasons) + approx_tokens(text)
        if cost > usable - used:  # truncate: keep leading lines that fit
            text, s, e = _excerpt(c, emitted, max(room * 4 - 8, 0))
            cost = _header_tokens(c, r.reasons) + approx_tokens(text)
            if cost > usable - used or not text:
                continue
        used += cost
        emitted |= {(c.path, n) for n in range(s, e + 1)} if c.kind != "config_key" else set()
        hits.append(
            ContextHit(
                node_id=r.hit_id or c.hit_id,
                kind=c.kind,
                path=c.path,
                start_line=max(s, 1),
                end_line=max(e, s, 1),
                score=round(r.score, 6),
                reasons=r.reasons,
                excerpt=text,
            )  # fmt: skip
        )
    return hits, used
