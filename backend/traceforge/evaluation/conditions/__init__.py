"""Experiment conditions. Contract names L0/G0/L1/G1: letter = retrieval (L|G), digit = feedback.

User aliases (Factor G level, Factor F level): G0F0=L0, G1F0=G0, G0F1=L1, G1F1=G1.
ARCHITECTURE.md agrees (Factor G: L vs G; Factor F: F0 vs F1); only the naming differs.
"""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

DIR = Path(__file__).parent
NAMES = ("L0", "G0", "L1", "G1")
ALIASES = {"G0F0": "L0", "G1F0": "G0", "G0F1": "L1", "G1F1": "G1"}


class Condition(BaseModel):
    name: Literal["L0", "G0", "L1", "G1"]
    alias: str
    retrieval: Literal["L", "G"]
    feedback: bool = Field(
        description="False = F0 (fresh attempts), True = F1 (visible-test feedback)"
    )
    model_id: str
    provider: str = Field(pattern=r"^[a-z0-9_-]+$")
    temperature: float = Field(ge=0, le=0)
    max_attempts: Literal[3]
    context_budget_chars: int = Field(gt=0)
    prompt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _consistent(self):
        if self.retrieval != self.name[0] or self.feedback != (self.name[1] == "1"):
            raise ValueError("name must equal retrieval letter + feedback digit")
        if ALIASES.get(self.alias) != self.name:
            raise ValueError("alias does not map to name")
        return self


def condition_sha256(c: Condition) -> str:
    return hashlib.sha256(json.dumps(c.model_dump(), sort_keys=True).encode()).hexdigest()


def load_condition(name: str, directory: Path = DIR) -> Condition:
    name = ALIASES.get(name, name)
    if name not in NAMES:
        raise ValueError(f"unknown condition {name!r}")
    return Condition.model_validate_json((directory / f"{name}.json").read_text("utf-8"))
