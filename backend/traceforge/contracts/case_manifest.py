"""CaseManifest: one fault case and its true answer. Produced by the fault generator (Track A)."""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

CauseClass = Literal[
    "configuration", "application_code", "runtime_dependency", "insufficient_evidence"
]
REPAIRABLE: frozenset[str] = frozenset({"configuration", "application_code"})


class GoldSymbol(BaseModel):
    """Where the cause lives in code. `path` is repo-relative POSIX, e.g. `lab/worker/queue.py`."""

    path: str = Field(pattern=r"^[^\\:]+$")
    qualname: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class CaseManifest(BaseModel):
    case_id: str
    split: Literal["dev", "test"]
    cause_class: CauseClass
    fault_family: str
    service: Literal["shop_api", "worker"]
    base_sha: str
    gold_config_keys: list[str] = []
    gold_symbols: list[GoldSymbol] = []
    distance: int | None = Field(
        default=None,
        ge=0,
        description="Graph hops from where the symptom shows to where the cause lives. "
        "None when there is no target (runtime_dependency, insufficient_evidence).",
    )
    reproducer_id: str
    visible_test_ids: list[str] = []
    hidden_test_ids: list[str] = []
    variant_group: str
    origin: Literal["synthetic", "bugsinpy"] = "synthetic"
    log_format: Literal["plain", "json", "uvicorn_access", "none"] = Field(
        default="plain", description="How the faulty service logs; results are broken down by it"
    )

    @model_validator(mode="after")
    def _repairable_needs_target(self) -> Self:
        if self.cause_class in REPAIRABLE:
            if not (self.gold_config_keys or self.gold_symbols):
                raise ValueError("a repairable case needs a gold config key or symbol")
            if self.distance is None:
                raise ValueError("a repairable case needs a distance")
            if not self.hidden_test_ids:
                raise ValueError("a repairable case needs hidden tests")
        return self
