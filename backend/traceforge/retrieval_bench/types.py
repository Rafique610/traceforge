# ruff: noqa: E501
"""Benchmark data types. Gold lives ONLY in `BenchQuery.gold` (scorer side); retrievers receive a
`QueryText`, which has no field that could carry it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from traceforge.contracts.evidence import EvidenceBundle

QUERY_TYPES = (
    "exact_identifier",
    "paraphrased_bug",
    "symptom_no_identifier",
    "indirect_dependency",
    "configuration",
    "multi_file",
)


class QueryText(str):
    """The query as a plain string (what a dense or lexical retriever embeds / tokenizes).

    Extra read-only attributes serve the existing L/G arms, which build anchors from an
    EvidenceBundle: `evidence` (synthetic single-item bundle for free-text queries, a rebuilt v5
    bundle for the dev split) and `service`. There is deliberately no gold, type or label field."""

    qid: str
    evidence: EvidenceBundle | None
    service: str

    def __new__(
        cls, text: str, qid: str = "", evidence: EvidenceBundle | None = None, service: str = ""
    ) -> QueryText:
        self = super().__new__(cls, text)
        self.qid, self.evidence, self.service = qid, evidence, service
        return self


@dataclass(frozen=True)
class GoldUnit:
    id: str  # chunk hit id: sym:<path>::<qualname> | test:<path>::<qualname> | cfg:<KEY>
    why: str = ""


@dataclass(frozen=True)
class BenchQuery:
    qid: str
    qtype: str  # one of QUERY_TYPES (free-text suites) or the cause class (dev)
    text: QueryText
    gold: frozenset[str]  # scorer side only
    meta: dict[str, Any] = field(default_factory=dict, compare=False)


def norm_gold_id(i: str) -> str:
    """`cfg:<service>.<KEY>` (manifest gold form) -> `cfg:<KEY>` (corpus hit id)."""
    if i.startswith("cfg:") and "." in i:
        return "cfg:" + i.split(".", 1)[1]
    return i
