"""Test helpers: hand-written UNIT-TEST evidence (not real collector output)."""

import hashlib

from traceforge.contracts.evidence import EvidenceBundle, EvidenceItem


def item(i: int, kind: str, content: str, service: str = "worker", **kw) -> EvidenceItem:
    return EvidenceItem(
        id=f"EV-{i:04d}", kind=kind, service=service, content=content,  # type: ignore[arg-type]
        sha256=hashlib.sha256(content.encode()).hexdigest(), **kw,
    )  # fmt: skip


def bundle(*items: EvidenceItem, incident_id: str = "inc-1") -> EvidenceBundle:
    return EvidenceBundle(
        incident_id=incident_id, base_sha="x", compose_sha256="0" * 64, items=list(items)
    )
