"""Source protocols (agreed signatures) and sample-JSON implementations.

Rafique's real producers (evidence collector, retrieval, code graph) plug in behind these.
"""

import json
from pathlib import Path
from typing import Any, Protocol

from traceforge.contracts.case_manifest import CaseManifest
from traceforge.contracts.context import ContextBundle
from traceforge.contracts.evidence import EvidenceBundle

SAMPLES = Path(__file__).resolve().parent.parent / "contracts" / "samples"


class CaseSource(Protocol):
    def get(self, case_id: str) -> CaseManifest: ...


class EvidenceSource(Protocol):
    def collect(
        self, incident_id: str, service: str, case: CaseManifest | None
    ) -> EvidenceBundle: ...


class ContextSource(Protocol):
    def retrieve(
        self, evidence: EvidenceBundle, graph: Any, mode: str, token_budget: int
    ) -> ContextBundle: ...

    def read_symbol(self, case: CaseManifest, path: str, qualname: str) -> str | None:
        """Source of a symbol at the case's base_sha, or None if it does not exist."""
        ...

    def neighbors(self, node_id: str) -> list[str]:
        """Code-map neighbours of a node (D22: offered in every condition)."""
        ...


def _alias(case_id: str) -> str:
    """Sample files are named by kind (code/config/abstain); accept either that or the case id."""
    for f in SAMPLES.glob("case_manifest.*.json"):
        if case_id in (f.suffixes[0][1:], json.loads(f.read_text("utf-8"))["case_id"]):
            return f.suffixes[0][1:]
    raise KeyError(f"no sample case {case_id!r}")


def _load(kind: str, alias: str) -> str:
    return (SAMPLES / f"{kind}.{alias}.json").read_text("utf-8")


class SampleCaseSource:
    def get(self, case_id: str) -> CaseManifest:
        return CaseManifest.model_validate_json(_load("case_manifest", _alias(case_id)))


class SampleEvidenceSource:
    def collect(self, incident_id: str, service: str, case: CaseManifest | None) -> EvidenceBundle:
        bundle = EvidenceBundle.model_validate_json(_load("evidence_bundle", _alias(case.case_id)))
        return bundle.model_copy(update={"incident_id": incident_id})


class SampleContextSource:
    def _bundle(self, alias: str) -> ContextBundle:
        return ContextBundle.model_validate_json(_load("context_bundle", alias))

    def retrieve(
        self, evidence: EvidenceBundle, graph: Any, mode: str, token_budget: int
    ) -> ContextBundle:
        """Sample bundles are fixed per case (found by evidence hashes); mode is stamped on."""
        shas = {i.sha256 for i in evidence.items}
        for f in SAMPLES.glob("evidence_bundle.*.json"):
            alias = f.suffixes[0][1:]
            other = EvidenceBundle.model_validate_json(f.read_text("utf-8"))
            if shas == {i.sha256 for i in other.items}:
                b = self._bundle(alias)
                return b.model_copy(update={"incident_id": evidence.incident_id, "mode": mode})
        raise KeyError("no sample context for this evidence")

    def read_symbol(self, case: CaseManifest, path: str, qualname: str) -> str | None:
        for hit in self._bundle(_alias(case.case_id)).hits:
            if hit.path == path and hit.node_id.endswith(f"::{qualname}"):
                return hit.excerpt
        return None

    def neighbors(self, node_id: str) -> list[str]:
        return []  # until the real code graph (P2-S02)
