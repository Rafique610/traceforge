"""Diagnose loop: evidence + context in, read-only tool calls, terminal submit_diagnosis.

Pipeline v4 (formal): 6 calls, every call counts, `diagnose_v1`. Unchanged.
Pipeline v5 (development track): `diagnose_v2` with the observed symptom, labelled evidence, a
workspace file index and `search_code`; 8 valid calls; a call rejected for a locally detectable
violation (bad arguments, over-long text, unsupported claim) does NOT consume the budget but is
capped (3 rejections, and an identical repeated rejection stops at once). Failure reasons stay
distinct: `insufficient_evidence` (model abstained), `invalid_output` (rejections exhausted),
`budget_exhausted` (valid calls used up). A rejected submission is never turned into a diagnosis.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from traceforge.agent import prompting
from traceforge.agent.evidence_view import LEGEND, is_symptom, render_evidence_v2
from traceforge.agent.gateway import GatewayError, ModelResponse
from traceforge.agent.tools import SubmitDiagnosis, ToolContext, ToolError, dispatch, tool_schemas
from traceforge.contracts.agent_run import Diagnosis
from traceforge.contracts.context import ContextBundle

TOOL_BUDGET = 6
TOOL_BUDGET_V5 = 8
MAX_REJECTED = 3
MAX_PROVIDER_FAILURES = 2
MAX_PROVIDER_FAILURES_V5 = 0  # dev-d1: the first provider failure stops the run (no extra requests)
REMINDER = "Respond with a tool call only. Call submit_diagnosis when done."
NO_SYMPTOM = (
    "No failing visible test was observed on the base commit. Rely on the logs, health and "
    "configuration evidence; do not invent a symptom."
)
ChatFn = Callable[..., ModelResponse]


@dataclass
class Usage:
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    cache_hits: int = 0
    list_price_usd: float = 0.0
    provider: str | None = None
    model: str | None = None

    def add(self, r: ModelResponse) -> None:
        self.tokens_in += r.tokens_in
        self.tokens_out += r.tokens_out
        self.latency_ms += r.latency_ms
        self.cache_hits += int(r.cache_hit)
        self.list_price_usd += r.list_price_usd or 0.0
        self.provider, self.model = r.provider, r.model


@dataclass
class DiagnoseResult:
    diagnosis: Diagnosis
    submitted: SubmitDiagnosis | None = None
    tool_calls: int = 0
    invalid_tool_calls: int = 0
    failure_reason: str | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)
    rejected: int = 0  # v5: calls rejected before counting (not part of tool_calls)


def _call_text(call: Any) -> str:
    """History entry for a call in the JSON shape the parser accepts (a small model imitates the
    history; a `tool_call NAME {...}` text format it cannot be parsed back from)."""
    try:
        args = json.loads(call.arguments or "{}")
    except ValueError:
        args = call.arguments
    return json.dumps({"name": call.name, "arguments": args})


def _abstain(
    reason: str, calls: int, invalid: int, trace: list, rejected: int = 0
) -> DiagnoseResult:
    d = Diagnosis(cause_class="insufficient_evidence", abstained=True)
    return DiagnoseResult(d, None, calls, invalid, reason, trace, rejected)


def _user_prompt_v5(tc: ToolContext, ctx: ContextBundle, budget_chars: int, system: str, user: str):
    from traceforge.contracts.evidence import EvidenceBundle

    symptom = [i for i in tc.evidence.items if is_symptom(i)]
    rest = EvidenceBundle(
        incident_id=tc.evidence.incident_id,
        base_sha=tc.evidence.base_sha,
        compose_sha256=tc.evidence.compose_sha256,
        items=[i for i in tc.evidence.items if not is_symptom(i)],
    )
    index = getattr(tc.ctx, "workspace_index", None)
    files = index(tc.case) if index else "(not available)"
    user = user.replace("{service}", tc.case.service)
    user = user.replace(
        "{symptom}",
        "\n\n".join(f"[{i.id}] {i.content}" for i in symptom) if symptom else NO_SYMPTOM,
    )
    user = user.replace("{evidence}", LEGEND + "\n" + render_evidence_v2(rest))
    user = user.replace("{files}", files)
    return system, user.replace("{context}", prompting.render_context(ctx, budget_chars))


def diagnose(
    tc: ToolContext,
    ctx: ContextBundle,
    chat_fn: ChatFn,
    usage: Usage,
    budget_chars: int,
    pipeline: str = "v4",
) -> DiagnoseResult:
    v5 = pipeline == "v5"
    system, user = prompting.load(prompting.PIPELINES[pipeline][0])
    if v5:
        system, user = _user_prompt_v5(tc, ctx, budget_chars, system, user)
    else:
        user = user.replace("{service}", tc.case.service)
        user = user.replace("{evidence}", prompting.render_evidence(tc.evidence))
        user = user.replace("{context}", prompting.render_context(ctx, budget_chars))
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    budget = TOOL_BUDGET_V5 if v5 else TOOL_BUDGET
    calls = invalid = reminders = failures = rejected = 0
    seen_rejected: set[str] = set()
    trace: list[dict[str, Any]] = []
    while calls < budget:
        try:
            resp = chat_fn(messages, tool_schemas(v5))
        except GatewayError as e:
            failures += 1
            if failures > (MAX_PROVIDER_FAILURES_V5 if v5 else MAX_PROVIDER_FAILURES):
                return _abstain(f"provider_error: {e}", calls, invalid, trace, rejected)
            continue
        usage.add(resp)
        if not resp.tool_calls:
            reminders += 1
            if reminders > 1:
                return _abstain("model_output_malformed", calls, invalid, trace, rejected)
            messages += [
                {"role": "assistant", "content": resp.content or ""},
                {"role": "user", "content": REMINDER},
            ]
            continue
        for call in resp.tool_calls:
            if calls >= budget:
                break
            if not v5:
                calls += 1
            try:
                out = dispatch(call.name, call.arguments, tc)
                if v5:
                    calls += 1
                trace.append({"tool": call.name, "ok": True})
            except ToolError as e:
                invalid += 1
                trace.append(
                    {"tool": call.name, "ok": False}
                    | ({"rejected": bool(e.schema), "error": str(e)[:400]} if v5 else {})
                )
                if v5 and e.schema:  # locally detectable: not counted, but capped
                    rejected += 1
                    key = hashlib.sha256(f"{call.name}{call.arguments}".encode()).hexdigest()
                    if key in seen_rejected or rejected > MAX_REJECTED:
                        return _abstain("invalid_output", calls, invalid, trace, rejected)
                    seen_rejected.add(key)
                    out = f"ERROR (does not count toward your tool budget): {e}"
                else:
                    if v5:
                        calls += 1
                    out = f"ERROR: {e}"
            if isinstance(out, SubmitDiagnosis):
                abstained = out.cause_class == "insufficient_evidence"
                d = Diagnosis(
                    cause_class=out.cause_class,
                    target=None if abstained else out.qualified_target(tc.case.service),
                    evidence_ids=out.supporting_evidence_ids,
                    contradicting_ids=out.contradicting_evidence_ids,
                    abstained=abstained,
                )
                return DiagnoseResult(
                    d,
                    out,
                    calls,
                    invalid,
                    "insufficient_evidence" if abstained else None,
                    trace,
                    rejected,
                )
            if v5 and calls == budget - 1:
                out = f"{out}\nNOTE: 1 tool call left: the next call must be submit_diagnosis."
            messages += [
                {"role": "assistant", "content": _call_text(call)},
                {"role": "user", "content": f"TOOL RESULT {call.name} (untrusted data):\n{out}"},
            ]
    return _abstain("budget_exhausted", calls, invalid, trace, rejected)
