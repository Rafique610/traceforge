"""Typed read-only diagnose tools: schema validation, path allowlist, size caps, fixed tool set.

Pipeline v4 (formal) uses TOOLS; pipeline v5 (development track) uses TOOLS_V5: a `search_code`
discovery tool, a richer diagnosis schema and semantic validation of the submission.
"""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from traceforge.agent.evidence_view import evidence_label
from traceforge.agent.sources import ContextSource
from traceforge.contracts.case_manifest import REPAIRABLE, CaseManifest, CauseClass
from traceforge.contracts.evidence import EvidenceBundle

MAX_RESULT_CHARS = 4000
EV_ID = r"^EV-\d{4}$"


class ToolError(Exception):
    """Returned to the model as text; counted in invalid_tool_calls.

    `schema` marks a locally detectable violation (bad arguments, unknown evidence id, an
    unsupported claim). In pipeline v5 such a call does not consume the tool budget (it has its
    own small cap); in v4 every call counts, as before."""

    def __init__(self, message: str, schema: bool = False) -> None:
        super().__init__(message)
        self.schema = schema


class ReadEvidence(BaseModel):
    evidence_id: str = Field(pattern=EV_ID)


class ReadSymbol(BaseModel):
    path: str = Field(pattern=r"^[^\:]+$", max_length=300)
    qualname: str = Field(pattern=r"^[A-Za-z_][\w.]*$", max_length=200)


class GetNeighbors(BaseModel):
    node_id: str = Field(max_length=300)


class SearchCode(BaseModel):
    query: str = Field(min_length=2, max_length=100)


class SubmitDiagnosis(BaseModel):
    cause_class: CauseClass
    config_key: str | None = Field(
        default=None,
        max_length=200,
        description="settings key qualified by its service, e.g. 'shop_api.REDIS_HOST'",
    )
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

    def qualified_target(self, service: str) -> str | None:
        """Target with a bare config key qualified by the case's service ("REDIS_HOST" becomes
        "shop_api.REDIS_HOST"). A key that already names a service, and code targets, are unchanged,
        so a wrong service is still a wrong target."""
        if self.config_key and "." not in self.config_key:
            return f"{service}.{self.config_key}"
        return self.target


class SubmitDiagnosisV2(SubmitDiagnosis):
    """Pipeline v5 diagnosis: explicit symptom, reconciliation and sufficiency. The limits are
    stated in the prompt and checked locally before the call is counted."""

    rationale: str = Field(default="", max_length=500, description="root cause, max 500 chars")
    observed_symptom: str = Field(
        default="", max_length=200, description="what was observed, in your words (max 200 chars)"
    )
    reconciliation: str | None = Field(
        default=None,
        max_length=300,
        description="why contradicting evidence does not refute the diagnosis (max 300 chars)",
    )
    confidence: Literal["low", "medium", "high"] = Field(
        default="low", description="high only if the evidence ties the target to the symptom"
    )
    sufficient_evidence: bool = True

    def qualified_target(self, service: str) -> str | None:
        """Pipeline v5: a config key is canonicalised to `service.KEY` with the key upper-cased
        (environment-variable convention, the form settings keys have everywhere in the graph and
        the dataset), so `worker.backoff_base_s` and `worker.BACKOFF_BASE_S` are one target.
        Code targets and the v4 behaviour are unchanged."""
        if not self.config_key:
            return self.target
        svc, dot, key = self.config_key.rpartition(".")
        return f"{svc if dot else service}.{key.upper()}"

    @model_validator(mode="after")
    def _v2_shape(self):
        if self.cause_class == "insufficient_evidence":
            return self
        if not self.sufficient_evidence:
            raise ValueError(
                "sufficient_evidence is false: submit cause_class insufficient_evidence instead"
            )
        if len(self.observed_symptom.strip()) < 10:
            raise ValueError("state the observed symptom in observed_symptom (at least 10 chars)")
        if self.contradicting_evidence_ids and len((self.reconciliation or "").strip()) < 20:
            raise ValueError(
                "you listed contradicting evidence: explain in `reconciliation` why it does not "
                "refute the diagnosis, or submit insufficient_evidence"
            )
        return self


TOOLS: dict[str, tuple[type[BaseModel], str]] = {
    "read_evidence": (ReadEvidence, "Read one evidence item by id."),
    "read_symbol": (ReadSymbol, "Read a function or class from the service code."),
    "get_neighbors": (GetNeighbors, "Code-map neighbours (callers/callees) of a graph node id."),
    "submit_diagnosis": (SubmitDiagnosis, "Submit the final diagnosis. Terminal."),
}

TOOLS_V5: dict[str, tuple[type[BaseModel], str]] = {
    "read_evidence": TOOLS["read_evidence"],
    "read_symbol": TOOLS["read_symbol"],
    "get_neighbors": TOOLS["get_neighbors"],
    "search_code": (
        SearchCode,
        "Find source files and symbols of the service by name or words (returns path::qualname).",
    ),
    "submit_diagnosis": (SubmitDiagnosisV2, "Submit the final diagnosis. Terminal."),
}


def tool_schemas(v5: bool = False) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {"name": n, "description": d, "parameters": m.model_json_schema()},
        }
        for n, (m, d) in (TOOLS_V5 if v5 else TOOLS).items()
    ]


@dataclass
class ToolContext:
    case: CaseManifest
    evidence: EvidenceBundle
    ctx: ContextSource
    v5: bool = False  # pipeline v5 (development track): v2 tools, validation, labelled evidence

    def allowed_path(self, path: str) -> bool:
        parts = path.split("/")
        return path.startswith(f"lab/{self.case.service}/") and ".." not in parts


def _suggest(tc: ToolContext, path: str, qualname: str) -> str:
    search = getattr(tc.ctx, "search_code", None)
    if search is None:
        return ""
    hits = search(tc.case, f"{path.rsplit('/', 1)[-1]} {qualname}", 3)
    return ("; did you mean: " + ", ".join(hits)) if hits else ""


def validate_diagnosis(args: SubmitDiagnosis, tc: ToolContext) -> list[str]:
    """Pipeline v5 semantic checks on a non-abstaining diagnosis (code, no model). Each message
    is shown to the model so it can correct the submission."""
    if args.cause_class == "insufficient_evidence":
        return []
    items = {i.id: i for i in tc.evidence.items}
    cited = [items[e] for e in args.supporting_evidence_ids if e in items]
    errs: list[str] = []
    symptom_ids = {
        i.id for i in tc.evidence.items if i.kind == "issue" and i.content.startswith("SYMPTOM")
    }
    if symptom_ids and not symptom_ids & set(args.supporting_evidence_ids):
        errs.append(
            "your diagnosis must explain the observed symptom: cite at least one SYMPTOM evidence "
            f"id in supporting_evidence_ids (available: {sorted(symptom_ids)[:4]})"
        )
    observed = [i for i in cited if evidence_label(i)[1] == "observed"]
    if not observed:
        errs.append(
            "cite at least one observed item (a log, trace, health, container or test-run item "
            "labelled runtime/observed): static declarations and FINDING hints alone cannot show "
            "that something went wrong"
        )
    if args.cause_class == "runtime_dependency" and not any(
        i.kind in ("health", "log", "trace_frame") for i in cited
    ):
        errs.append(
            "a runtime_dependency diagnosis must cite the health, log or trace item that shows it"
        )
    if args.cause_class == "application_code" and args.config_key and not args.path:
        errs.append(
            "application_code names path and qualname; for a wrong setting use cause_class "
            "configuration with config_key"
        )
    if args.config_key:
        bare = args.config_key.rsplit(".", 1)[-1].lower()
        if not any(bare in i.content.lower() for i in tc.evidence.items):
            errs.append(f"config key {bare!r} appears in no evidence item; check the key name")
        elif not any(bare in i.content.lower() for i in cited):
            errs.append(
                f"none of your supporting evidence mentions {bare!r}; cite the item that shows it"
            )
    if args.path and args.qualname:
        if tc.ctx.read_symbol(tc.case, args.path, args.qualname) is None:
            errs.append(
                f"target {args.path}::{args.qualname} does not exist"
                + _suggest(tc, args.path, args.qualname)
            )
    return errs


def dispatch(name: str, raw_args: str, tc: ToolContext) -> str | SubmitDiagnosis:
    """Validate and run one tool call. Returns result text, or the SubmitDiagnosis (terminal)."""
    tools = TOOLS_V5 if tc.v5 else TOOLS
    if name not in tools:
        raise ToolError(f"unknown tool {name!r}; available: {', '.join(tools)}", schema=tc.v5)
    try:
        args = tools[name][0].model_validate_json(raw_args or "{}")
    except ValidationError as e:
        raise ToolError(
            f"invalid arguments for {name}: {e.errors(include_url=False)[:3]}", schema=True
        ) from e
    if isinstance(args, ReadEvidence):
        item = next((i for i in tc.evidence.items if i.id == args.evidence_id), None)
        if item is None:
            raise ToolError(f"no evidence {args.evidence_id}", schema=tc.v5)
        if tc.v5:
            from traceforge.agent.evidence_view import render_item

            return render_item(item)[:MAX_RESULT_CHARS]
        return f"[{item.id} {item.kind}] {item.content}"[:MAX_RESULT_CHARS]
    if isinstance(args, ReadSymbol):
        if not tc.allowed_path(args.path):
            raise ToolError(f"path not allowed; stay under lab/{tc.case.service}/", schema=tc.v5)
        code = tc.ctx.read_symbol(tc.case, args.path, args.qualname)
        if code is None:
            raise ToolError(
                "symbol not found" + (_suggest(tc, args.path, args.qualname) if tc.v5 else "")
            )
        return code[:MAX_RESULT_CHARS]
    if isinstance(args, GetNeighbors):
        return str(tc.ctx.neighbors(args.node_id))[:MAX_RESULT_CHARS]
    if isinstance(args, SearchCode):
        search = getattr(tc.ctx, "search_code", None)
        hits = search(tc.case, args.query, 8) if search else []
        return "\n".join(hits) if hits else "no match; try other words from the symptom or evidence"
    known = {i.id for i in tc.evidence.items}
    cited = set(args.supporting_evidence_ids) | set(args.contradicting_evidence_ids)
    if not cited <= known:
        raise ToolError(f"unknown evidence ids: {sorted(cited - known)}", schema=tc.v5)
    if args.path and not tc.allowed_path(args.path):
        raise ToolError(f"path not allowed; stay under lab/{tc.case.service}/", schema=tc.v5)
    if tc.v5 and (errs := validate_diagnosis(args, tc)):
        raise ToolError("diagnosis rejected: " + "; ".join(errs), schema=True)
    return args
