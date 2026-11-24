"""Evidence rendering for pipeline v5: every item keeps its id, kind, service, origin and location,
and says whether it is a STATIC declaration or a RUNTIME observation.

Rules (confirmed root cause C of the diagnosis investigation): the v4 renderer printed
`[id kind service] content` and dropped path/line, so a default declared in `settings.py`
(`db_host='localhost'`) looked like the running service's value. Here:
  - a default declared in source is `static/declared`;
  - a compose service definition is `static/declared` (never claimed as the effective value);
  - the container environment from `docker inspect` is `runtime/observed`, but is NOT the value of
    the application's Settings object (the collector never observes that);
  - logs, health probes, trace frames and test runs are `runtime/observed`.
Items carrying explicit `scope/basis/origin` (new collector output) keep them; older bundles get
the same labels derived from `kind` and `path`, so saved evidence files stay usable unchanged.
"""

from traceforge.contracts.evidence import EvidenceBundle, EvidenceItem

EVIDENCE_ITEM_CHARS = 1500
SYMPTOM_TAG = "SYMPTOM"

LEGEND = (
    "Evidence labels: `static/declared` = written in a source or compose file; it says what is "
    "declared, NOT what the running service uses. `runtime/observed` = seen in a running "
    "container, log, probe or test run. A compose or default value is never proof of the value "
    "the application actually loaded; only an observed runtime item can show that. Items "
    "starting `FINDING` are hints from deterministic rules over the other items (they cite "
    "their evidence ids): they point at where to look, they are not verdicts, and a hint that "
    "does not connect to the symptom is to be ignored."
)


def is_symptom(item: EvidenceItem) -> bool:
    return item.kind == "issue" and item.content.startswith(SYMPTOM_TAG)


def evidence_label(item: EvidenceItem) -> tuple[str, str, str]:
    """(scope, basis, origin) for an item: explicit fields win, else derived from kind/path."""
    scope, basis, origin = item.scope, item.basis, item.origin
    if scope and basis and origin:
        return scope, basis, origin
    if item.kind == "config" and item.path:
        d = ("static", "declared", "default declared in the settings source (not a runtime value)")
    elif item.kind == "config":
        d = ("runtime", "observed", "container environment at start; not the app's Settings object")
    elif item.kind == "compose":
        d = ("static", "declared", "compose file service definition (declared, not verified)")
    elif item.kind == "health":
        d = ("runtime", "observed", "container state or HTTP probe")
    elif item.kind in ("log", "trace_frame"):
        d = ("runtime", "observed", "service log")
    elif is_symptom(item):
        d = ("runtime", "observed", "visible test run on the base commit")
    else:
        d = ("runtime", "observed", "reported")
    return scope or d[0], basis or d[1], origin or d[2]


def render_item(item: EvidenceItem) -> str:
    scope, basis, origin = evidence_label(item)
    where = (
        f" {item.path}:{item.line}"
        if item.path and item.line
        else (f" {item.path}" if item.path else "")
    )
    head = f"[{item.id} {item.kind} {item.service} | {scope}/{basis} |{where.strip() or '-'}]"
    note = f" (origin: {origin})" if item.kind in ("config", "compose") else ""
    return f"{head} {item.content[:EVIDENCE_ITEM_CHARS]}{note}"


def render_evidence_v2(evidence: EvidenceBundle) -> str:
    """Symptom items first (what happened), then the rest in id order."""
    items = sorted(evidence.items, key=lambda i: (not is_symptom(i), i.id))
    return "\n".join(render_item(i) for i in items)
