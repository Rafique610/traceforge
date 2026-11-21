"""Diagnose loop: evidence + context in, read-only tool calls (<=6), terminal submit_diagnosis."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from traceforge.agent import prompting
from traceforge.agent.gateway import GatewayError, ModelResponse
from traceforge.agent.tools import SubmitDiagnosis, ToolContext, ToolError, dispatch, tool_schemas
from traceforge.contracts.agent_run import Diagnosis
from traceforge.contracts.context import ContextBundle

TOOL_BUDGET = 6
MAX_PROVIDER_FAILURES = 2
REMINDER = "Respond with a tool call only. Call submit_diagnosis when done."
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


def _call_text(call: Any) -> str:
    """History entry for a call in the JSON shape the parser accepts (a small model imitates the
    history; a `tool_call NAME {...}` text format it cannot be parsed back from)."""
    try:
        args = json.loads(call.arguments or "{}")
    except ValueError:
        args = call.arguments
    return json.dumps({"name": call.name, "arguments": args})


def _abstain(reason: str, calls: int, invalid: int, trace: list) -> DiagnoseResult:
    d = Diagnosis(cause_class="insufficient_evidence", abstained=True)
    return DiagnoseResult(d, None, calls, invalid, reason, trace)


def diagnose(
    tc: ToolContext, ctx: ContextBundle, chat_fn: ChatFn, usage: Usage, budget_chars: int
) -> DiagnoseResult:
    system, user = prompting.load("diagnose_v1")
    user = user.replace("{service}", tc.case.service)
    user = user.replace("{evidence}", prompting.render_evidence(tc.evidence))
    user = user.replace("{context}", prompting.render_context(ctx, budget_chars))
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    calls = invalid = reminders = failures = 0
    trace: list[dict[str, Any]] = []
    while calls < TOOL_BUDGET:
        try:
            resp = chat_fn(messages, tool_schemas())
        except GatewayError as e:
            failures += 1
            if failures > MAX_PROVIDER_FAILURES:
                return _abstain(f"provider_error: {e}", calls, invalid, trace)
            continue
        usage.add(resp)
        if not resp.tool_calls:
            reminders += 1
            if reminders > 1:
                return _abstain("model_output_malformed", calls, invalid, trace)
            messages += [
                {"role": "assistant", "content": resp.content or ""},
                {"role": "user", "content": REMINDER},
            ]
            continue
        for call in resp.tool_calls:
            if calls >= TOOL_BUDGET:
                break
            calls += 1
            try:
                out = dispatch(call.name, call.arguments, tc)
                trace.append({"tool": call.name, "ok": True})
            except ToolError as e:
                invalid += 1
                out = f"ERROR: {e}"
                trace.append({"tool": call.name, "ok": False})
            if isinstance(out, SubmitDiagnosis):
                abstained = out.cause_class == "insufficient_evidence"
                d = Diagnosis(
                    cause_class=out.cause_class,
                    target=None if abstained else out.target,
                    evidence_ids=out.supporting_evidence_ids,
                    contradicting_ids=out.contradicting_evidence_ids,
                    abstained=abstained,
                )
                return DiagnoseResult(
                    d, out, calls, invalid, "insufficient_evidence" if abstained else None, trace
                )
            messages += [
                {"role": "assistant", "content": _call_text(call)},
                {"role": "user", "content": f"TOOL RESULT {call.name} (untrusted data):\n{out}"},
            ]
    return _abstain("budget_exhausted", calls, invalid, trace)
