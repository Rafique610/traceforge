import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traceforge.incidents.states import State

Source = Literal["lab_case", "manual", "github"]


class IncidentCreate(BaseModel):
    case_id: str | None = Field(default=None, min_length=1, max_length=128)
    service: str | None = Field(default=None, min_length=1, max_length=128)
    symptom: str | None = Field(default=None, min_length=1, max_length=10_000)
    source: Source | None = None  # defaults: lab_case when case_id is given, else manual

    @model_validator(mode="after")
    def _case_or_symptom(self) -> Self:
        if not self.case_id and not (self.symptom and self.service):
            raise ValueError("provide case_id, or both symptom and service")
        return self


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: str | None
    service: str | None
    symptom: str | None
    source: Source
    state: State
    cause_class: str | None
    base_sha: str | None
    created_at: datetime
    updated_at: datetime


class IncidentPage(BaseModel):
    items: list[IncidentOut]
    total: int
    limit: int
    offset: int


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: uuid.UUID
    actor: str
    event_type: str
    from_state: State | None
    to_state: State | None
    payload: dict
    payload_sha256: str
    created_at: datetime


class EvidenceItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: uuid.UUID
    kind: str
    service: str
    content: str
    sha256: str
    path: str | None
    line: int | None
    ts: datetime | None
