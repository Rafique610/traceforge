"""RC2 fix (a): an over-long diagnosis `rationale` is truncated, not rejected.

RC1 rejects a submit_diagnosis whose rationale exceeds 500 chars (`string_too_long`), which ended
shop_api-019/-030 as invalid output. The tolerant handler rewrites the tool-call arguments before
RC1 validation sees them, so no extra request and no attempt is spent. The original text is logged.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

RATIONALE_LIMIT = 500  # SubmitDiagnosisV2.rationale max_length


def truncate_rationale(raw_args: str, log: list[dict[str, Any]] | None = None) -> str:
    """Return the arguments JSON with `rationale` cut to the limit (unchanged if not applicable)."""
    try:
        args = json.loads(raw_args or "{}")
    except ValueError:
        return raw_args
    r = args.get("rationale") if isinstance(args, dict) else None
    if not isinstance(r, str) or len(r) <= RATIONALE_LIMIT:
        return raw_args
    if log is not None:
        log.append({"event": "rationale_truncated", "original_len": len(r), "original": r})
    args["rationale"] = r[: RATIONALE_LIMIT - 3].rstrip() + "..."
    return json.dumps(args)


def tolerant_rationale(
    chat_fn: Callable[..., Any], log: list[dict[str, Any]]
) -> Callable[..., Any]:
    def wrapped(messages, tools=None, **kw):
        resp = chat_fn(messages, tools, **kw)
        if not tools or not resp.tool_calls:
            return resp
        calls = [
            c.model_copy(update={"arguments": truncate_rationale(c.arguments, log)})
            if c.name == "submit_diagnosis"
            else c
            for c in resp.tool_calls
        ]
        return resp.model_copy(update={"tool_calls": calls})

    return wrapped
