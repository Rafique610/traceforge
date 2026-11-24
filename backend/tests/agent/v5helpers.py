"""Hand-written evidence builders for the v5 tests (unique module name: no conftest clash)."""

import hashlib

from traceforge.contracts.evidence import EvidenceBundle, EvidenceItem


def item(i: int, kind: str, content: str, service: str = "shop_api", **kw) -> EvidenceItem:
    return EvidenceItem(
        id=f"EV-{i:04d}",
        kind=kind,  # type: ignore[arg-type]
        service=service,
        content=content,
        sha256=hashlib.sha256(content.encode()).hexdigest(),
        **kw,
    )


def bundle(*items: EvidenceItem) -> EvidenceBundle:
    return EvidenceBundle(
        incident_id="inc-1", base_sha="x", compose_sha256="0" * 64, items=list(items)
    )
