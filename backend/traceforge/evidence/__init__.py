"""Evidence collector: failing lab -> redacted, SHA-pinned EvidenceBundle (read-only)."""

from traceforge.evidence.collector import Collection, EvidenceCollector, collect
from traceforge.evidence.model import EvidenceConfig

__all__ = ["Collection", "EvidenceCollector", "EvidenceConfig", "collect"]
