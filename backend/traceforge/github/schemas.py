from pydantic import BaseModel, ConfigDict, Field

from traceforge.incidents.schemas import IncidentOut


class GitHubIntake(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=300)
    service: str | None = Field(default=None, min_length=1, max_length=128)


class GitHubIntakeOut(BaseModel):
    incident: IncidentOut
    evidence_id: str
    evidence_sha256: str
    untrusted: bool = True
