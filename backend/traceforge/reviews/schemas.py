import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=1, max_length=80)
    patch_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description="Required when the incident has a frozen patch; omit for no-patch outcomes",
    )
    comment: str | None = Field(default=None, max_length=2000)


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    patch_sha256: str | None
    decision: Literal["approve", "reject"]
    reviewer: str
    comment: str | None
    created_at: datetime
