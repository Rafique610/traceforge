"""The rules. Pure functions of an evidence bundle; deterministic; conservative.

Every rule returns zero or more `Finding`s. A rule that cannot tie its statement to cited
evidence ids does not fire. Wording stays at "the evidence shows / look at": no rule names a fix.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from traceforge.contracts.evidence import EvidenceBundle, EvidenceItem

FINDING_TAG = "FINDING"
MAX_FINDINGS = 8
MAX_FINDING_CHARS = 600

_SYMPTOM = "SYMPTOM"


@dataclass(frozen=True)
class Finding:
    rule: str
    text: str  # one or two sentences, no tag
    evidence_ids: tuple[str, ...]
    terms: tuple[str, ...] = field(default=())  # words worth searching for (keys, hosts)

    def render(self) -> str:
        ids = ", ".join(self.evidence_ids)
        return f"{FINDING_TAG} [{self.rule}] {self.text} (evidence: {ids})"[:MAX_FINDING_CHARS]


def is_finding(item: EvidenceItem) -> bool:
    return item.kind == "issue" and item.content.startswith(FINDING_TAG)


def _is_symptom(item: EvidenceItem) -> bool:
    return item.kind == "issue" and item.content.startswith(_SYMPTOM)


# --- parsed views of the evidence --------------------------------------------------------------

_DECL = re.compile(r"^settings\.(\w+) \[([^\]]*)\](?: = (.*))?$", re.S)
_CONTAINER = re.compile(
    r"^container (\S+): (\w+) \(health: (\w+)\)(?:, restart_count=(\d+))?(?:, exit_code=(-?\d+))?"
)
_ENV = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")


@dataclass(frozen=True)
class Decl:
    item: EvidenceItem
    name: str  # lower-case settings field
    type: str
    raw: str | None  # printed default, None when the field has none

    @property
    def number(self) -> Decimal | None:
        return _number(self.raw)

    @property
    def text_value(self) -> str | None:
        if self.raw and len(self.raw) >= 2 and self.raw[0] == self.raw[-1] and self.raw[0] in "'\"":
            return self.raw[1:-1]
        return None


def _number(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    m = re.fullmatch(r"(?:Decimal\(['\"](.+?)['\"]\)|(-?\d+(?:\.\d+)?))", raw.strip())
    if not m:
        return None
    try:
        return Decimal(m.group(1) or m.group(2))
    except InvalidOperation:
        return None


def _decls(ev: EvidenceBundle) -> list[Decl]:
    out = []
    for i in ev.items:
        if i.kind == "config" and i.path:
            m = _DECL.match(i.content.strip())
            if m:
                out.append(Decl(i, m.group(1).lower(), m.group(2), m.group(3)))
    return out


def _runtime_env(ev: EvidenceBundle) -> list[tuple[EvidenceItem, str, str]]:
    out = []
    for i in ev.items:
        if i.kind == "config" and not i.path:
            m = _ENV.match(i.content.strip())
            if m:
                out.append((i, m.group(1), m.group(2)))
    return out


def _compose_services(ev: EvidenceBundle) -> dict[str, EvidenceItem]:
    out = {}
    for i in ev.items:
        if i.kind == "compose":
            m = re.match(r"service (\S+)", i.content)
            if m:
                out[m.group(1)] = i
    return out


def _compose_env(item: EvidenceItem) -> dict[str, str]:
    m = re.search(r"^environment: (.*)$", item.content, re.M)
    out = {}
    for part in (m.group(1) if m else "").split(", "):
        k, eq, v = part.partition("=")
        if eq and re.fullmatch(r"[A-Z][A-Z0-9_]*", k):
            out[k] = v
    return out


def _containers(ev: EvidenceBundle) -> list[tuple[EvidenceItem, str, str, int, int | None]]:
    """(item, state, health, restart_count, exit_code) per container health item."""
    out = []
    for i in ev.items:
        if i.kind == "health":
            m = _CONTAINER.match(i.content)
            if m:
                out.append((i, m.group(2), m.group(3), int(m.group(4) or 0), _int(m.group(5))))
    return out


def _int(s: str | None) -> int | None:
    return int(s) if s is not None else None


def _logs(ev: EvidenceBundle) -> list[EvidenceItem]:
    return [i for i in ev.items if i.kind in ("log", "trace_frame")]


# --- rule: a container is down or unhealthy ----------------------------------------------------


def rule_container_down(ev: EvidenceBundle) -> list[Finding]:
    bad = [
        (i, st, hl, rc, ec)
        for i, st, hl, rc, ec in _containers(ev)
        if st not in ("running",) or hl == "unhealthy" or rc >= 3
    ]
    out = []
    for i, st, hl, rc, ec in bad:
        svc = i.service
        mentions = [
            x.id
            for x in _logs(ev)
            if x.service != svc and re.search(rf"(?<![\w-]){re.escape(svc)}(?![\w-])", x.content)
        ]
        extra = f"; errors in other evidence name {svc} as a host" if mentions else ""
        detail = f"exit code {ec}" if ec is not None and st != "running" else f"{rc} restarts"
        out.append(
            Finding(
                "container_down",
                f"the container of service {svc} is {st} (health: {hl}, {detail}){extra}. "
                "Errors in services that depend on it can be consequences; check whether the "
                "symptom is explained by it or by something else.",
                (i.id, *mentions[:2]),
                (svc,),
            )
        )
    return out


# --- rule: hostname resolution failed ----------------------------------------------------------

_NAME_FAIL = re.compile(
    r"Name or service not known|gaierror|Temporary failure in name resolution|"
    r"nodename nor servname|getaddrinfo failed|could not translate host name",
    re.I,
)
_HOST_PATTERNS = (
    re.compile(r"connecting to ([A-Za-z0-9_.-]+):\d+"),
    re.compile(r'could not translate host name "([^"]+)"', re.I),
    re.compile(r"(?:host|hostname)[ =:]+['\"]?([A-Za-z0-9_.-]+)['\"]?", re.I),
    re.compile(r"\b([A-Za-z0-9_.-]+\.(?:internal|local|svc|lan))\b"),
)


def _failed_hosts(ev: EvidenceBundle) -> list[tuple[str, EvidenceItem]]:
    found: list[tuple[str, EvidenceItem]] = []
    for i in _logs(ev):
        if not _NAME_FAIL.search(i.content):
            continue
        for pat in _HOST_PATTERNS:
            for m in pat.finditer(i.content):
                h = m.group(1).strip(".")
                if h and h.lower() not in ("none", "localhost") and (h, i) not in found:
                    found.append((h, i))
    return found


def rule_hostname_resolution(ev: EvidenceBundle) -> list[Finding]:
    services = _compose_services(ev)
    decls = _decls(ev)
    out: list[Finding] = []
    seen: set[str] = set()
    for host, log_item in _failed_hosts(ev):
        if host in seen:
            continue
        seen.add(host)
        ids = [log_item.id]
        if host in services:
            down = [
                i.id
                for i, st, hl, _rc, _ec in _containers(ev)
                if i.service == host and (st != "running" or hl == "unhealthy")
            ]
            if down:  # resolution failed because the container is gone: container_down covers it
                out.append(
                    Finding(
                        "hostname_unresolved",
                        f"the name {host!r} could not be resolved although it is a compose "
                        f"service; the container of {host} is not running healthy.",
                        (log_item.id, *down),
                        (host,),
                    )
                )
            continue
        svc_list = ", ".join(sorted(services)) or "none found"
        parts = [
            f"the name {host!r} could not be resolved and is not a compose service "
            f"(compose services: {svc_list})."
        ]
        keys: list[str] = []
        for d in decls:
            if d.text_value == host:
                ids.append(d.item.id)
                keys.append(d.name)
                parts.append(f"The settings default of {d.name} declares exactly this name.")
                env_key = d.name.upper()
                for sname, sitem in services.items():
                    val = _compose_env(sitem).get(env_key)
                    if val is not None and val in services:
                        ids.append(sitem.id)
                        parts.append(
                            f"Compose service {sname} sets {env_key}={val}, a compose service"
                            + (
                                f"; the compose environment of {d.item.service} does not set it."
                                if env_key not in _compose_env(services.get(d.item.service, sitem))
                                and d.item.service in services
                                else "."
                            )
                        )
                        break
        out.append(Finding("hostname_unresolved", " ".join(parts), tuple(ids[:5]), (host, *keys)))
    return out


# --- rule: startup validation names a settings key ---------------------------------------------

_VALIDATION = re.compile(r"(\d+) validation errors? for (\w+)\n((?:[ \t]*\w+\n[ \t]+.+\n?)+)", re.M)
_VAL_FIELD = re.compile(r"^[ \t]*(\w+)\n[ \t]+(.+)$", re.M)


def rule_startup_validation(ev: EvidenceBundle) -> list[Finding]:
    out = []
    for i in _logs(ev):
        m = _VALIDATION.search(i.content + "\n")
        if not m:
            continue
        fields = [(f, msg.strip()[:60]) for f, msg in _VAL_FIELD.findall(m.group(3))]
        if not fields:
            continue
        names = ", ".join(f"{f} ({msg})" for f, msg in fields[:4])
        out.append(
            Finding(
                "startup_validation",
                f"startup validation of {m.group(2)} failed for: {names}. The named settings "
                "fields (or their environment variables) are where to look.",
                (i.id,),
                tuple(f for f, _ in fields[:4]),
            )
        )
    return out


# --- rule: import / syntax errors with a location ----------------------------------------------

_CODE_ERR = re.compile(
    r"^(ModuleNotFoundError|ImportError|SyntaxError|IndentationError|NameError|"
    r"AttributeError|TypeError|KeyError|ValueError|ZeroDivisionError)\b: ?(.*)$",
    re.M,
)
_FILE_LINE = re.compile(r'File "([^"]+)", line (\d+)')
_STATIC_ERRORS = ("ModuleNotFoundError", "ImportError", "SyntaxError", "IndentationError")


def rule_code_error_location(ev: EvidenceBundle) -> list[Finding]:
    """Import/syntax errors (they name a file and a line at start-up) with the innermost file:line
    that is not site-packages or the standard library."""
    out = []
    for i in (x for x in ev.items if x.kind == "log"):
        for m in _CODE_ERR.finditer(i.content):
            if m.group(1) not in _STATIC_ERRORS:
                continue
            frames = [
                (p, ln)
                for p, ln in _FILE_LINE.findall(i.content[: m.start()])
                if "site-packages" not in p and "/usr/local/lib" not in p and "<frozen" not in p
            ]
            where = f" at {frames[-1][0]}:{frames[-1][1]}" if frames else ""
            out.append(
                Finding(
                    "code_error_location",
                    f"{m.group(1)}: {m.group(2)[:120]}{where}. This fails when the module is "
                    "loaded, so the service cannot start from that file as it is.",
                    (i.id,),
                    (m.group(1),),
                )
            )
            break
    return out


# --- rule: configuration values that are implausible for what their name says ------------------

_NEVER_NEGATIVE = re.compile(
    r"(^|_)(delay|backoff|timeout|retry|retries|attempts|interval|ttl|size|port|count|level|"
    r"limit|max|min|wait|period|seconds|s)($|_)"
)
_RATIO = re.compile(r"(^|_)(rate|ratio|fraction|probability)($|_)")
_PERCENT = re.compile(r"(^|_)(pct|percent|percentage)($|_)")
_MONEY_PEER = re.compile(r"(^|_)(fee|price|cost|amount|charge|over|threshold|total|shipping)($|_)")
_MONEY = re.compile(r"(^|_)(fee|price|cost|amount|charge)($|_)")


def _implausible(d: Decl) -> str | None:
    n = d.number
    if n is None:
        return None
    if n < 0 and _NEVER_NEGATIVE.search(d.name):
        return f"{d.name} defaults to {d.raw}, a negative value for a count, size, delay or limit"
    if n == 0 and re.search(r"(^|_)(delay|backoff|timeout|interval|ttl|wait|period)($|_)", d.name):
        return f"{d.name} defaults to {d.raw}, zero for a delay, timeout or interval"
    if _RATIO.search(d.name) and n > 1:
        return f"{d.name} defaults to {d.raw}, a ratio above 1"
    if _PERCENT.search(d.name) and n > 100:
        return f"{d.name} defaults to {d.raw}, a percentage above 100"
    if _PERCENT.search(d.name) and n == 100 and re.search(r"(^|_)(max|cap|limit)($|_)", d.name):
        return f"{d.name} defaults to 100, which makes a maximum percentage no limit at all"
    return None


def _failing_signal(ev: EvidenceBundle) -> bool:
    """A failing visible test, or an error-bearing log: settings checks only matter then."""
    for i in ev.items:
        if _is_symptom(i) and "failing test" in i.content.split("\n", 1)[0]:
            return True
    return any(
        re.search(r"Traceback|\bERROR\b|\bCRITICAL\b", i.content)
        for i in ev.items
        if i.kind == "log"
    )


def rule_implausible_default(ev: EvidenceBundle) -> list[Finding]:
    if not _failing_signal(ev):
        return []
    decls = _decls(ev)
    out = []
    for d in decls:
        why = _implausible(d)
        if why:
            out.append(
                Finding(
                    "implausible_default",
                    f"{why}. It is declared in {d.item.path}; check whether it matches the "
                    "observed values.",
                    (d.item.id,),
                    (d.name,),
                )
            )
    # money fields: one integer-valued fee next to decimal-valued peers may be in other units
    money = [d for d in decls if _MONEY.search(d.name) and d.number is not None]
    peers = [d for d in decls if _MONEY_PEER.search(d.name) and d.number is not None]
    if any(d.raw and "." in d.raw for d in peers):
        for d in money:
            if d.raw and "." not in d.raw and d.number is not None and d.number >= 100:
                out.append(
                    Finding(
                        "implausible_default",
                        f"{d.name} defaults to {d.raw}, an integer-valued money amount of 100 or "
                        "more next to money settings written with decimals; the unit may differ.",
                        (d.item.id,),
                        (d.name,),
                    )
                )
    return out


_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def rule_symptom_sign(ev: EvidenceBundle) -> list[Finding]:
    """The code under test produced the negation of a required number, and a settings default is
    negative: those two facts together."""
    neg = [d for d in _decls(ev) if d.number is not None and d.number < 0]
    if not neg:
        return []
    for i in ev.items:
        if not _is_symptom(i):
            continue
        m = re.search(r"compared: left=(.*?) right=(.*?) \(left = ", i.content)
        if not m:
            continue
        left, right = _NUM.findall(m.group(1)), _NUM.findall(m.group(2))
        if left and len(left) == len(right):
            pairs = [(Decimal(a), Decimal(b)) for a, b in zip(left, right, strict=True)]
            if any(a < 0 and a == -b for a, b in pairs):
                names = ", ".join(f"{d.name}={d.raw}" for d in neg[:3])
                return [
                    Finding(
                        "symptom_sign",
                        "the value produced is the negation of the value the test requires, "
                        f"and a settings default is negative ({names}).",
                        (i.id, *[d.item.id for d in neg[:3]]),
                        tuple(d.name for d in neg[:3]),
                    )
                ]
    return []


def _differing_pairs(item: EvidenceItem) -> list[tuple[Decimal, Decimal]]:
    m = re.search(r"compared: left=(.*?) right=(.*?) \(left = ", item.content)
    if not m:
        return []
    left, right = _NUM.findall(m.group(1)), _NUM.findall(m.group(2))
    if not left or len(left) != len(right):  # abbreviated or differently shaped: skip
        return []
    pairs = [(Decimal(a), Decimal(b)) for a, b in zip(left, right, strict=True)]
    return [(a, b) for a, b in pairs if a != b]


def _power_of_ten(x: Decimal) -> bool:
    if x <= 0 or x == 1:
        return False
    return Decimal(10) ** x.log10().to_integral_value() == x


def rule_symptom_value_is_default(ev: EvidenceBundle) -> list[Finding]:
    """A number the code under test produced is the required number scaled by a power of ten
    (a unit error) and is exactly a settings default; at most 3 matching settings, so the finding
    narrows the search instead of listing the settings file."""
    decls = [d for d in _decls(ev) if d.number is not None]
    for i in ev.items:
        if not _is_symptom(i):
            continue
        produced = {a for a, b in _differing_pairs(i) if b != 0 and _power_of_ten(abs(a / b))}
        hit = [d for d in decls if d.number in produced]
        if 0 < len(hit) <= 3:
            names = ", ".join(f"{d.name}={d.raw}" for d in hit)
            return [
                Finding(
                    "symptom_value_is_default",
                    "a value the code under test produced is the value the test requires times "
                    f"a power of ten, and equals the declared default of: {names}. The value may "
                    "come from such a setting; check that the code on the failing path reads it.",
                    (i.id, *[d.item.id for d in hit]),
                    tuple(d.name for d in hit),
                )
            ]
    return []


# --- rule: a name setting that differs between services ----------------------------------------

_SHARED_NAME = re.compile(r"(^|_)(queue|topic|channel|stream|exchange)($|_)")


def rule_name_mismatch(ev: EvidenceBundle) -> list[Finding]:
    """Queue-like settings that two services read from the same key but resolve to different
    names (runtime environment wins over the declared default)."""
    env: dict[tuple[str, str], tuple[str, str]] = {}  # (service, key) -> (value, evidence id)
    for i, k, v in _runtime_env(ev):
        env[(i.service, k.lower())] = (v, i.id)
    eff: dict[str, dict[str, tuple[str, str, str]]] = {}  # key -> service -> (value, id, source)
    comp: dict[tuple[str, str], tuple[str, str]] = {}  # (service, key) -> (value, compose item id)
    for name, citem in _compose_services(ev).items():
        for k, v in _compose_env(citem).items():
            if _SHARED_NAME.search(k.lower()) and not v.startswith("$"):
                comp[(name, k.lower())] = (v, citem.id)
    for d in _decls(ev):
        if _SHARED_NAME.search(d.name) and d.text_value is not None:
            val, eid, src = d.text_value, d.item.id, "settings default"
            if (d.item.service, d.name) in env:
                val, eid = env[(d.item.service, d.name)]
                src = "container environment"
            elif (d.item.service, d.name) in comp:
                val, eid = comp[(d.item.service, d.name)]
                src = "compose environment"
            eff.setdefault(d.name, {})[d.item.service] = (val, eid, src)
    for (svc, key), (val, eid) in comp.items():  # services whose settings are not in the evidence
        if key in eff and svc not in eff[key]:
            eff[key][svc] = (val, eid, "compose environment")
    out = []
    for key, by_svc in sorted(eff.items()):
        if len({v for v, _e, _s in by_svc.values()}) > 1:
            parts = [f"{s}: {v!r} ({src})" for s, (v, _e, src) in sorted(by_svc.items())]
            out.append(
                Finding(
                    "name_mismatch",
                    f"services read the setting {key} but it resolves to different names: "
                    + "; ".join(parts)
                    + ". A producer and a consumer that use different names never meet.",
                    tuple(e for _v, e, _s in by_svc.values()),
                    (key,),
                )
            )
    return out


# --- rule: nothing failing and nothing unhealthy ------------------------------------------------

_SUMMARY = re.compile(r"(\w+): (\d+) failed, (\d+) passed")


def rule_nothing_observed(ev: EvidenceBundle) -> list[Finding]:
    """Abstention hint: visible suites ran and everything passed, containers are healthy and the
    logs hold no error. Needs the symptom summary, so it never fires without a test run."""
    summary = next(
        (i for i in ev.items if _is_symptom(i) and "summary of the base commit" in i.content), None
    )
    if summary is None:
        return []
    runs = _SUMMARY.findall(summary.content)
    if not runs or any(int(f) > 0 for _s, f, _p in runs):
        return []
    if any(_is_symptom(i) and "failing test" in i.content.split("\n", 1)[0] for i in ev.items):
        return []
    conts = _containers(ev)
    if any(st != "running" or hl == "unhealthy" or rc >= 3 for _i, st, hl, rc, _e in conts):
        return []
    for i in ev.items:
        if i.kind == "log" and re.search(r"Traceback|\bERROR\b|\bCRITICAL\b|Exception", i.content):
            return []
        if i.kind == "health" and re.search(
            r"-> (4|5)\d\d|degraded|\"(db|redis|worker)\":\s*\"(?!ok)", i.content
        ):
            return []
    ids = (summary.id, *[i.id for i, *_ in conts][:3])
    return [
        Finding(
            "nothing_observed",
            "the visible tests all pass on this commit, every container is healthy and no log "
            "holds an error. The evidence shows no failure to explain; if no item ties a "
            "location to a reported problem, abstaining is appropriate.",
            ids,
        )
    ]


RULES: tuple[Callable[[EvidenceBundle], list[Finding]], ...] = (
    rule_container_down,
    rule_hostname_resolution,
    rule_startup_validation,
    rule_code_error_location,
    rule_symptom_sign,
    rule_symptom_value_is_default,
    rule_implausible_default,
    rule_name_mismatch,
    rule_nothing_observed,
)


def run_rules(evidence: EvidenceBundle) -> list[Finding]:
    """All findings, in rule order, de-duplicated and bounded. A failing rule never breaks the
    pipeline: it is skipped."""
    out: list[Finding] = []
    for rule in RULES:
        try:
            out += rule(evidence)
        except Exception:  # noqa: BLE001 - diagnostics are advisory; never fail the run
            continue
    seen: set[str] = set()
    uniq = []
    signed = {t for f in out if f.rule == "symptom_sign" for t in f.terms}
    for f in out:
        if f.rule == "implausible_default" and set(f.terms) <= signed:
            continue  # the stronger finding about the same setting already says it
        if f.text not in seen:
            seen.add(f.text)
            uniq.append(f)
    return uniq[:MAX_FINDINGS]


def findings_as_items(evidence: EvidenceBundle, findings: list[Finding]) -> list[EvidenceItem]:
    """Evidence items for `findings`, ids continuing after the bundle's last id."""
    service = evidence.items[0].service if evidence.items else ""
    nxt = max((int(i.id[3:]) for i in evidence.items), default=0)
    items = []
    for n, f in enumerate(findings, start=1):
        text = f.render()
        items.append(
            EvidenceItem(
                id=f"EV-{nxt + n:04d}",
                kind="issue",
                service=service,
                content=text,
                sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                scope="runtime",
                basis="inferred",
                origin="deterministic rule over the collected evidence (a hint, not a verdict)",
            )
        )
    return items
