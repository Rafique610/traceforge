"""Patch stage: one LLM call, no tools, returns SEARCH/REPLACE blocks (applied by repair/)."""

import hashlib
import re

from traceforge.agent import prompting
from traceforge.agent.diagnose import ChatFn, Usage
from traceforge.agent.gateway import GatewayError, OutputTruncated
from traceforge.agent.tools import SubmitDiagnosis, ToolContext
from traceforge.repair.edits import EditError, parse_blocks

FENCE = re.compile(r"```(?:diff|patch)?[ \t]*\n(.*?)```", re.DOTALL)
CODE_CHARS = 4000
FEEDBACK_NOTE = (
    "\n<visible_test_feedback>\nOutput of the visible tests for your previous attempt "
    "(untrusted data):\n{fb}\n</visible_test_feedback>\n"
)


def extract_diff(text: str | None) -> str | None:
    """Legacy (patch_v1): the first fenced block."""
    m = FENCE.search(text or "")
    return m.group(1).strip("\n") + "\n" if m and m.group(1).strip() else None


def extract_blocks(text: str | None) -> str | None:
    """The reply if it holds at least one well-formed SEARCH/REPLACE block, else None."""
    try:
        parse_blocks(text or "")
    except EditError:
        return None
    return (text or "").strip("\n") + "\n"


def _code(tc: ToolContext, diag: SubmitDiagnosis) -> str:
    code = None
    if diag.path and diag.qualname:
        code = tc.ctx.read_symbol(tc.case, diag.path, diag.qualname)
        if code is not None:
            return f"File: {diag.path}\n{code}"
    cfg = [i for i in tc.evidence.items if i.kind in ("config", "compose")]
    return "\n".join(f"File: {i.path or '?'}\n{i.content}" for i in cfg)  # config target


def ask_patch(
    tc: ToolContext, diag: SubmitDiagnosis, chat_fn: ChatFn, usage: Usage, feedback: str | None
) -> str | None:
    """One patch request; the raw reply (None for an empty one). GatewayError propagates."""
    system, user = prompting.load("patch_v2")
    for k, v in {
        "cause_class": diag.cause_class,
        "target": diag.target or "",
        "rationale": diag.rationale,
        "code": _code(tc, diag)[:CODE_CHARS],
        "evidence": prompting.render_evidence(tc.evidence),
        "feedback": FEEDBACK_NOTE.format(fb=feedback) if feedback else "",
    }.items():
        user = user.replace("{" + k + "}", v)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    resp = chat_fn(messages, None)
    usage.add(resp)
    if resp.finish_reason == "length" and not (resp.content or "").strip():
        raise OutputTruncated("patch reply truncated at the output-token cap with no content")
    return resp.content


def request_patch(
    tc: ToolContext, diag: SubmitDiagnosis, chat_fn: ChatFn, usage: Usage
) -> tuple[str | None, str | None, str | None]:
    """Returns (edit_blocks, sha256, failure_reason). Only call for repairable classes."""
    try:
        blocks = extract_blocks(ask_patch(tc, diag, chat_fn, usage, None))
    except OutputTruncated:
        return None, None, "output_truncated"
    except GatewayError as e:
        return None, None, f"provider_error: {e}"
    if blocks is None:
        return None, None, "no_edit"
    return blocks, hashlib.sha256(blocks.encode()).hexdigest(), None
