"""RC2 fix (c): deterministic, model-free config-value diagnostic.

Flags a host/port-like value that a candidate edit introduces when it matches no compose service
name and no setting key/value known from the visible evidence (shop_api-020: `lab_redis`).
Visible evidence only: reads the EvidenceBundle (logs/compose/config), never tests.

Integration point (not wired into RC1): the RC1 evidence is built before any edit exists, so the
flag can only reach the model as visible feedback on a later request. `repeat_guard` includes it in
its re-ask note; surfacing it for every attempt needs a hook in `agent/patch.py::ask_patch` or
`repair/feedback.py` (both frozen RC1 files), so that part is left undone.
"""

from __future__ import annotations

import re

from traceforge.contracts.evidence import EvidenceBundle
from traceforge.repair.edits import EditBlock

_KEYLINE = re.compile(
    r"""^\s*["']?(?P<key>[\w.\-]*(?:host|addr|url|server|broker|endpoint|dsn|port)[\w.\-]*)["']?"""
    r"""\s*[:=,(]\s*(?P<val>.+?)\s*,?\s*$""",
    re.I,
)
_VAL = re.compile(r"""["'](?P<s>[^"']+)["']|(?P<n>\b\d{2,5}\b)""")
ALWAYS_OK = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def known_names(ev: EvidenceBundle) -> set[str]:
    """Compose service names, environment keys and values, ports, and config setting names."""
    out: set[str] = set(ALWAYS_OK)
    for i in ev.items:
        if i.kind == "compose":
            if m := re.match(r"service (\S+)", i.content):
                out.add(m.group(1))
            for part in re.findall(r"^environment: (.*)$", i.content, re.M):
                for kv in part.split(", "):
                    k, eq, v = kv.partition("=")
                    if eq:
                        out |= {k.strip(), v.strip()}
            out |= set(re.findall(r"\b(\d{2,5})\b", i.content))
        elif i.kind == "config":
            out |= set(re.findall(r"\b([A-Z][A-Z0-9_]{2,})\b", i.content))
    return {x for x in out if x}


def _added_lines(b: EditBlock) -> list[str]:
    old = {ln.strip() for ln in b.old.splitlines()}
    return [ln for ln in b.new.splitlines() if ln.strip() not in old]


def check_edit_values(blocks: list[EditBlock], ev: EvidenceBundle) -> list[str]:
    """One message per introduced host/port value unknown to the visible compose/settings."""
    known = known_names(ev)
    hosts = ", ".join(sorted(k for k in known if not k.isupper() and not k.isdigit())) or "none"
    msgs: list[str] = []
    for b in blocks:
        for ln in _added_lines(b):
            m = _KEYLINE.match(ln)
            if not m:
                continue
            for v in _VAL.finditer(m["val"]):
                val = v["s"] or v["n"]
                if val in known or val.startswith(("$", "{", "%")):
                    continue
                if v["s"] and not re.fullmatch(r"[A-Za-z][\w.\-]*", val):
                    continue
                msgs.append(
                    f"{b.path}: value '{val}' for '{m['key']}' matches no compose service or "
                    f"setting in the visible evidence (known: {hosts})"
                )
    return msgs
