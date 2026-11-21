"""Typed read-only diagnose tools: schema validation, path allowlist, size caps, fixed tool set."""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator

from traceforge.agent.sources import ContextSource
from traceforge.contracts.case_manifest import REPAIRABLE, CaseManifest, CauseClass
from traceforge.contracts.evidence import EvidenceBundle

MAX_RESULT_CHARS = 4000
EV_ID = r"^EV-\d{4}$"


class ToolError(Exception):
    """Returned to the model as text; counted in invalid_tool_calls."""


class ReadEvidence(BaseModel):
    evidence_id: str = Field(pattern=EV_ID)


class ReadSymbol(BaseModel):
    path: str = Field(pattern=r"^[^\:]+$", max_length=300)
    qualname: str = Field(pattern=r"^[A-Za-z_][\w.]*$", max_length=200)


class GetNeighbors(BaseModel):
    node_id: str = Field(max_length=300)


class SubmitDiagnosis(BaseModel):
    cause_class: CauseClass
    config_key: str | None = Field(default=None, max_length=200)
    path: str | None = Field(default=None, pattern=r"^[^\:]+$", max_length=300)
    qualname: str | None = Field(default=None, max_length=200)
    supporting_evidence_ids: list[str] = Field(default=[], max_length=20)
    contradicting_evidence_ids: list[str] = Field(default=[], max_length=20)
    rationale: str = Field(default="", max_length=600)

    @model_validator(mode="after")
    def _shape(self):
        abstain = self.cause_class == "insufficient_evidence"
        if not abstain and not self.supporting_evidence_ids:
            raise ValueError("cite at least one supporting evidence id")
        if self.cause_class in REPAIRABLE and not (
            self.config_key or (self.path and self.qualname)
        ):
            raise ValueError("a repairable diagnosis needs config_key or path+qualname")
        return self

    @property
    def target(self) -> str | None:
        return self.config_key or (f"{self.path}::{self.qualname}" if self.path else None)


TOOLS: dict[str, tuple[type[BaseModel], str]] = {
    "read_evidence": (ReadEvidence, "Read one evidence item by id."),
    "read_symbol": (ReadSymbol, "Read a function or class from the service code."),
    "get_neighbors": (GetNeighbors, "Code-map neighbours (callers/callees) of a graph node id."),
    "submit_diagnosis": (SubmitDiagnosis, "Submit the final diagnosis. Terminal."),
}


def tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {"name": n, "description": d, "parameters": m.model_json_schema()},
        }
        for n, (m, d) in TOOLS.items()
    ]


@dataclass
class ToolContext:
    case: CaseManifest
    evidence: EvidenceBundle
    ctx: ContextSource

    def allowed_path(self, path: str) -> bool:
        parts = path.split("/")
        return path.startswith(f"lab/{self.case.service}/") and ".." not in parts


def dispatch(name: str, raw_args: str, tc: ToolContext) -> str | SubmitDiagnosis:
    """Validate and run one tool call. Returns result text, or the SubmitDiagnosis (terminal)."""
    if name not in TOOLS:
        raise ToolError(f"unknown tool {name!r}; available: {', '.join(TOOLS)}")
    try:
        args = TOOLS[name][0].model_validate_json(raw_args or "{}")
    except ValidationError as e:
        raise ToolError(f"invalid arguments for {name}: {e.errors(include_url=False)[:3]}") from e
    if isinstance(args, ReadEvidence):
        item = next((i for i in tc.evidence.items if i.id == args.evidence_id), None)
        if item is None:
            raise ToolError(f"no evidence {args.evidence_id}")
        return f"[{item.id} {item.kind}] {item.content}"[:MAX_RESULT_CHARS]
    if isinstance(args, ReadSymbol):
        if not tc.allowed_path(args.path):
            raise ToolError(f"path not allowed; stay under lab/{tc.case.service}/")
        code = tc.ctx.read_symbol(tc.case, args.path, args.qualname)
        if code is None:
            raise ToolError("symbol not found")
        return code[:MAX_RESULT_CHARS]
    if isinstance(args, GetNeighbors):
        return str(tc.ctx.neighbors(args.node_id))[:MAX_RESULT_CHARS]
    known = {i.id for i in tc.evidence.items}
    cited = set(args.supporting_evidence_ids) | set(args.contradicting_evidence_ids)
    if not cited <= known:
        raise ToolError(f"unknown evidence ids: {sorted(cited - known)}")
    if args.path and not tc.allowed_path(args.path):
        raise ToolError(f"path not allowed; stay under lab/{tc.case.service}/")
    return args
