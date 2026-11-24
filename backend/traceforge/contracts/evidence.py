"""EvidenceBundle: read-only facts about one incident. Produced by the evidence collector (Track A).

`content` is already redacted. `path` is repo-relative POSIX.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    id: str = Field(pattern=r"^EV-\d{4}$")
    kind: Literal["log", "health", "config", "trace_frame", "compose", "issue"]
    service: str
    content: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    path: str | None = Field(default=None, pattern=r"^[^\\:]+$")
    line: int | None = Field(default=None, ge=1)
    ts: datetime | None = None
    # Provenance (pipeline v5). Optional so existing bundles stay valid; `evidence_label` in
    # traceforge/agent/evidence_view.py derives the same labels from kind/path when these are None.
    scope: Literal["static", "runtime"] | None = None  # written in files vs seen in a run
    basis: Literal["declared", "observed", "inferred"] | None = None
    origin: str | None = Field(default=None, max_length=120)  # where the content came from


class EvidenceBundle(BaseModel):
    incident_id: str
    base_sha: str
    compose_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    items: list[EvidenceItem]
