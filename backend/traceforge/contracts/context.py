"""ContextBundle: ranked code and config snippets for one incident. Produced by retrieval (Track A).

`path` is repo-relative POSIX.
"""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator


class ContextHit(BaseModel):
    node_id: str
    kind: Literal["symbol", "config_key", "test", "file"]
    path: str = Field(pattern=r"^[^\\:]+$")
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    score: float
    reasons: list[str]
    excerpt: str


class ContextBundle(BaseModel):
    incident_id: str
    mode: Literal["L", "G"]
    token_budget: int = Field(gt=0)
    tokens_used: int = Field(ge=0)
    hits: list[ContextHit]

    @model_validator(mode="after")
    def _within_budget(self) -> Self:
        if self.tokens_used > self.token_budget:
            raise ValueError("tokens_used exceeds token_budget")
        return self
