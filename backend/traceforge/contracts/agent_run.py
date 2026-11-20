"""AgentRunRecord: everything one agent run did, enough to recompute every metric (Track B)."""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from traceforge.contracts.case_manifest import CauseClass


class Diagnosis(BaseModel):
    cause_class: CauseClass
    target: str | None = Field(
        default=None, description="`path::qualname` for code, or the config key; None if abstained"
    )
    evidence_ids: list[str] = []
    contradicting_ids: list[str] = []
    abstained: bool = False

    @model_validator(mode="after")
    def _abstain_consistent(self) -> Self:
        if self.abstained != (self.cause_class == "insufficient_evidence"):
            raise ValueError(
                "abstained must be true exactly when cause_class is insufficient_evidence"
            )
        if not self.abstained and not self.evidence_ids:
            raise ValueError("a non-abstaining diagnosis must cite evidence_ids")
        return self


class AgentRunRecord(BaseModel):
    run_id: str
    case_id: str
    condition: Literal["L0", "G0", "L1", "G1"]
    model_id: str
    provider: Literal["mistral", "ollama", "groq"]
    prompt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    diagnosis: Diagnosis
    patch_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    attempts: int = Field(ge=0, le=3)
    outcome: Literal["TEST_VERIFIED_IN_LAB", "REJECTED", "UNVERIFIED", "NO_PATCH"]
    hidden_passed: bool | None = None
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    cost_usd: float = Field(ge=0, description="What was actually paid (0 on free tiers)")
    list_price_usd: float = Field(ge=0, description="Paid-tier equivalent at list price")
    latency_ms: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    invalid_tool_calls: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    git_sha: str

    @model_validator(mode="after")
    def _outcome_consistent(self) -> Self:
        if self.outcome == "NO_PATCH" and self.patch_sha256 is not None:
            raise ValueError("NO_PATCH runs cannot carry a patch")
        if self.outcome == "TEST_VERIFIED_IN_LAB" and self.hidden_passed is not True:
            raise ValueError("TEST_VERIFIED_IN_LAB requires hidden_passed true")
        return self
