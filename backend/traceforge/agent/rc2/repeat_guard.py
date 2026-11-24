"""RC2 fix (b): identical-repeat guard for the patch loop (shop_api-020: `lab_redis` x3).

Wraps the chat function. A patch reply (a call with no tools) whose SEARCH/REPLACE blocks equal an
earlier reply's blocks is a no-progress attempt: it is not passed on. The model is re-asked once
with a note built only from visible information (the visible-evidence config diagnostic); if the
second reply is again identical, an empty reply is returned (RC1 treats it as no
edit) and the reason
`no_progress_identical_edit` is logged. Hidden-test content is never available here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from traceforge.contracts.evidence import EvidenceBundle
from traceforge.repair.edits import EditError, parse_blocks

from .config_check import check_edit_values

NOTE = (
    "\n<no_progress_notice>\nYour reply repeats an edit you already proposed, which did not make "
    "the visible tests pass. Propose a DIFFERENT edit (a different new value or location), "
    "using only the evidence above.\n{extra}</no_progress_notice>\n"
)


def edit_key(text: str | None) -> tuple | None:
    try:
        return tuple((b.path, b.old.strip(), b.new.strip()) for b in parse_blocks(text or ""))
    except EditError:
        return None


def repeat_guard(
    chat_fn: Callable[..., Any], log: list[dict[str, Any]], evidence: EvidenceBundle | None = None
) -> Callable[..., Any]:
    seen: set[tuple] = set()

    def wrapped(messages, tools=None, **kw):
        resp = chat_fn(messages, tools, **kw)
        if tools:  # diagnosis call, not a patch reply
            return resp
        key = edit_key(resp.content)
        if key is None:
            return resp
        if key not in seen:
            seen.add(key)
            return resp
        extra = ""
        if evidence is not None:
            flags = check_edit_values(parse_blocks(resp.content or ""), evidence)
            extra = "".join(f"Note: {f}\n" for f in flags)
        log.append({"event": "identical_edit_rejected", "asked_again": True})
        msgs = [dict(m) for m in messages]
        msgs[-1]["content"] = msgs[-1]["content"] + NOTE.format(extra=extra)
        resp2 = chat_fn(msgs, tools, **kw)
        k2 = edit_key(resp2.content)
        if k2 == key:
            log.append(
                {"event": "no_progress_identical_edit", "reason": "no_progress_identical_edit"}
            )
            return resp2.model_copy(update={"content": ""})
        if k2 is not None:
            seen.add(k2)
        return resp2

    return wrapped
