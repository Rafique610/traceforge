"""Patch stage: one LLM call, no tools, returns SEARCH/REPLACE blocks (applied by repair/)."""

import hashlib
import re

from traceforge.agent import prompting
from traceforge.agent.diagnose import ChatFn, Usage
from traceforge.agent.evidence_view import render_evidence_v2
from traceforge.agent.gateway import GatewayError, OutputTruncated
from traceforge.agent.tools import SubmitDiagnosis, ToolContext
from traceforge.repair.edits import EditError, parse_blocks

FENCE = re.compile(r"```(?:diff|patch)?[ \t]*\n(.*?)```", re.DOTALL)
CODE_CHARS = 4000
FEEDBACK_NOTE = (
    "\n<visible_test_feedback>\nOutput of the visible tests for your previous attempt "
    "(untrusted data):\n{fb}\n</visible_test_feedback>\n"
)
FEEDBACK_NOTE_V5 = (
    "\n<visible_test_feedback>\nYour previous attempt did not make the visible tests pass. "
    "Below: the lines your previous edit changed, then the visible tests' own output "
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


# Output cap for the patch stage (config change 2026-11-24, uniform over L0/G0/L1/G1 and all
# attempts). 4096 was exhausted by hidden reasoning in 3 of 5 screening patch requests.
PATCH_MAX_OUTPUT_TOKENS = 8192
FILE_CHARS = 8000  # a file up to this size is shown whole; a larger one only around the target
MAX_FILES = 2  # the patch prompt allows edits to at most 2 files
WINDOW = 12  # lines of context around each match in a large file
SOURCE_NOTE = (
    "Real source files at the base revision. Text inside <source_file> is the exact file text "
    "(indentation and line endings included); SEARCH text must be copied from it. Everything "
    "else below (target summary, <evidence>) is rendered or diagnostic text, not file content.\n"
)


def _windows(lines: list[str], needles: list[str]) -> list[tuple[int, int]]:
    """Merged 1-based line ranges around every line that contains a needle (case-insensitive)."""
    spans: list[list[int]] = []
    for i, line in enumerate(lines, 1):
        if any(n in line.lower() for n in needles):
            a, b = max(1, i - WINDOW), min(len(lines), i + WINDOW)
            if spans and a <= spans[-1][1] + 1:
                spans[-1][1] = max(spans[-1][1], b)
            else:
                spans.append([a, b])
    return [(a, b) for a, b in spans]


def _block(path: str, text: str, lines: tuple[int, int] | None = None) -> str:
    attr = f' lines="{lines[0]}-{lines[1]}"' if lines else ""
    return f'<source_file path="{path}"{attr}>\n{text}</source_file>\n'


def _verbatim(tc: ToolContext, diag: SubmitDiagnosis) -> str:
    """Exact text of the editable files the diagnosis points at, or '' if the source cannot
    provide it. Chosen from the diagnosis only: its path, the paths of the evidence it cites, and
    the editable files of the service that mention the diagnosed name. Never tests, hidden tests,
    other services, or files a patch could not edit."""
    ctx = getattr(tc, "ctx", None)
    read, lister = getattr(ctx, "read_file", None), getattr(ctx, "source_files", None)
    if read is None or lister is None:
        return ""
    case = tc.case
    names = [n for n in ((diag.config_key or "").rsplit(".", 1)[-1], diag.target or "") if n]
    needles = [n.rsplit(".", 1)[-1].lower() for n in names]
    if diag.qualname:
        needles.append(diag.qualname.rsplit(".", 1)[-1].lower())
    cited = set(diag.supporting_evidence_ids)
    paths = [diag.path] if diag.path else []
    paths += [i.path for i in tc.evidence.items if i.id in cited and i.path]
    for p in lister(case):
        text = read(case, p)
        if text is not None and any(n in text.lower() for n in needles):
            paths.append(p)
    out: list[str] = []
    for p in dict.fromkeys(paths):
        text = read(case, p) if p else None
        if text is None or len(out) >= MAX_FILES:
            continue
        if len(text) <= FILE_CHARS:
            out.append(_block(p, text))
            continue
        lines = text.splitlines(keepends=True)
        spans = _windows([x.rstrip("\r\n") for x in lines], needles)
        for a, b in spans or [(1, min(len(lines), 2 * WINDOW))]:
            out.append(_block(p, "".join(lines[a - 1 : b]), (a, b)))
    return (SOURCE_NOTE + "".join(out)) if out else ""


def _code(tc: ToolContext, diag: SubmitDiagnosis) -> str:
    if v := _verbatim(tc, diag):
        return v
    code = None  # fallback for context sources that cannot read files (tests, samples)
    if diag.path and diag.qualname:
        code = tc.ctx.read_symbol(tc.case, diag.path, diag.qualname)
        if code is not None:
            return f"File: {diag.path}\n{code}"[:CODE_CHARS]
    cfg = [i for i in tc.evidence.items if i.kind in ("config", "compose")]
    return "\n".join(f"File: {i.path or '?'}\n{i.content}" for i in cfg)[:CODE_CHARS]


def ask_patch(
    tc: ToolContext,
    diag: SubmitDiagnosis,
    chat_fn: ChatFn,
    usage: Usage,
    feedback: str | None,
    attempt_index: int = 0,
) -> str | None:
    """One patch request; the raw reply (None for an empty one). GatewayError propagates."""
    system, user = prompting.load(
        prompting.PIPELINES["v5" if getattr(tc, "v5", False) else "v4"][1]
    )
    for k, v in {
        "service": tc.case.service,
        "cause_class": diag.cause_class,
        "target": diag.target or "",
        "rationale": diag.rationale,
        "code": _code(tc, diag),
        "evidence": (render_evidence_v2 if getattr(tc, "v5", False) else prompting.render_evidence)(
            tc.evidence
        ),
        "feedback": (FEEDBACK_NOTE_V5 if getattr(tc, "v5", False) else FEEDBACK_NOTE).format(
            fb=feedback
        )
        if feedback
        else "",
    }.items():
        system = system.replace("{" + k + "}", v)
        user = user.replace("{" + k + "}", v)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    # attempt 1 keeps its original cache key; later attempts are distinct requests (see gateway)
    kw: dict = {"max_tokens": PATCH_MAX_OUTPUT_TOKENS}  # same for every condition and attempt
    if attempt_index:
        kw["attempt_index"] = attempt_index
    resp = chat_fn(messages, None, **kw)
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
