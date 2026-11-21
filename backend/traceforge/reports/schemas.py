"""Report model. Every field is copied from a stored row; nothing is model-generated."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

RootCauseStatus = Literal["SUPPORTED", "INCONCLUSIVE", "RUNTIME_DEPENDENCY", "NOT_DIAGNOSED"]


class Header(BaseModel):
    incident_id: uuid.UUID
    case_id: str | None
    service: str | None
    base_sha: str | None
    origin: str
    state: str
    created_at: datetime


class EvidenceRef(BaseModel):
    id: str
    kind: str
    service: str
    path: str | None
    line: int | None
    sha256: str


class RootCause(BaseModel):
    status: RootCauseStatus
    cause_class: str | None
    target: str | None
    evidence_ids: list[str]


class Hypothesis(BaseModel):
    cause_class: str | None = None
    target: str | None = None
    supporting_ids: list[str] = []
    contradicting_ids: list[str] = []


class PatchView(BaseModel):
    sha256: str
    paths: list[str]
    diff: str
    signature_changed: bool
    impact: list[dict]


class ValidationView(BaseModel):
    attempt: int
    suite: str
    passed: int
    failed: int
    outcome: str
    tests: list[dict]


class ReviewView(BaseModel):
    id: uuid.UUID
    decision: str
    reviewer: str
    patch_sha256: str | None
    comment: str | None
    created_at: datetime


class OutcomeView(BaseModel):
    """Per outcome class: dependency (runtime_dependency) or missing evidence (insufficient)."""

    outcome_class: str | None
    dependency: str | None = None
    dependency_evidence_ids: list[str] = []
    missing_evidence: list[str] = []


class Report(BaseModel):
    header: Header
    symptom: str | None
    symptom_evidence_ids: list[str]
    root_cause: RootCause
    outcome: OutcomeView
    evidence: list[EvidenceRef]
    hypotheses: list[Hypothesis]
    patch: PatchView | None
    validation_runs: list[ValidationView]
    model_usage: dict | None
    review: ReviewView | None
    limitations: str
