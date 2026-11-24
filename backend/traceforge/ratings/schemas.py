from pydantic import BaseModel, Field

Score = Field(ge=1, le=5)


class RatingIn(BaseModel):
    rater: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.@ -]+$")
    cause_clear: int = Score
    evidence_convincing: int = Score
    patch_understandable: int = Score
    would_approve: int = Score
    note: str | None = Field(default=None, max_length=1000)


class RatingOut(RatingIn):
    incident_id: str
    report_sha256: str
    created_at: str


class RatingSummary(BaseModel):
    n: int
    mean: dict[str, float | None]
