"""Deterministic rule baseline: evidence -> cause class + target. No model, no randomness.

Rules, first match wins:
 1. A connection error names host H (log/trace text). If H is a Compose service whose health item
    is not running-healthy -> runtime_dependency.
 2. Else if a config item binds a KEY to a value containing H and H is not a healthy service ->
    configuration, target `<service>.<KEY>`.
 3. Else (connection error, nothing binds H) -> runtime_dependency (dependency absent).
 4. Else, if a trace_frame item has a path -> application_code, target `<path>::<function>` of the
    innermost (last) frame. The frame's function name is all the evidence gives, so class
    qualifiers are not recovered (a documented limit of this baseline).
 5. Else insufficient_evidence (abstain).
"""

import re

from traceforge.contracts.agent_run import AgentRunRecord, Diagnosis
from traceforge.contracts.case_manifest import CaseManifest
from traceforge.contracts.evidence import EvidenceBundle, EvidenceItem

CONNECTION_RE = re.compile(
    r"connection ?(?:refused|error|reset)|name or service not known|getaddrinfo|"
    r"cannot reach|could not connect|connecting to|timed? ?out connecting",
    re.I,
)
HOST_RE = re.compile(r"(?:\bat|\bto|host=)\s*['\"]?([A-Za-z0-9][A-Za-z0-9_.-]*):\d+")
HEALTH_RE = re.compile(r"container\s+(\S+)-\d+:\s*(.*)", re.I)
FRAME_FN_RE = re.compile(r"\bin ([A-Za-z_][\w.<>]*)")
CONFIG_LINE_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*[=:]\s*(.+?)\s*$", re.M)


def _health(items: list[EvidenceItem]) -> dict[str, bool]:
    """service -> running healthy, from `container <proj>-<service>-<n>: <state>` items."""
    out = {}
    for it in items:
        if it.kind == "health" and (m := HEALTH_RE.search(it.content)):
            state = m.group(2).lower()
            out[m.group(1).rsplit("-", 1)[-1]] = state.startswith("running") and (
                "unhealthy" not in state
            )
    return out


def _conn_error(items: list[EvidenceItem]) -> tuple[str, list[str]] | None:
    for it in items:
        if it.kind in ("log", "trace_frame") and CONNECTION_RE.search(it.content):
            if m := HOST_RE.search(it.content):
                return m.group(1), [it.id]
    return None


def _answer(cls: str, target: str | None, ids: list[str]) -> Diagnosis:
    return Diagnosis(cause_class=cls, target=target, evidence_ids=ids)  # type: ignore[arg-type]


def diagnose_by_rules(bundle: EvidenceBundle) -> Diagnosis:
    items = bundle.items
    health = _health(items)
    if (conn := _conn_error(items)) is not None:
        host, ids = conn
        health_ids = [i.id for i in items if i.kind == "health" and f"-{host}-" in i.content]
        if host in health and not health[host]:
            return _answer("runtime_dependency", None, ids + health_ids)
        if not health.get(host):
            for it in items:
                if it.kind != "config":
                    continue
                for key, value in CONFIG_LINE_RE.findall(it.content):
                    if host in value:
                        return _answer("configuration", f"{it.service}.{key}", ids + [it.id])
            return _answer("runtime_dependency", None, ids)
    frames = [it for it in items if it.kind == "trace_frame" and it.path]
    if frames:
        top = frames[-1]
        fns = FRAME_FN_RE.findall(top.content)
        if fns:
            return _answer("application_code", f"{top.path}::{fns[-1]}", [top.id])
    return Diagnosis(cause_class="insufficient_evidence", abstained=True)


def baseline_records(
    bundles: dict[str, EvidenceBundle],
    manifests: list[CaseManifest],
    dataset_sha256: str,
    git_sha: str = "rules-baseline",
) -> list[AgentRunRecord]:
    """One record per case with condition "RULES", scored by the same metrics as agent runs.

    The AgentRunRecord contract only allows L0/G0/L1/G1; RULES records are built with
    `model_construct` (no validation) until the contract gains a `RULES` condition value.
    Cost, tokens and latency are real zeros (a deterministic function); outcome is NO_PATCH.
    """
    out = []
    for m in manifests:
        if m.case_id not in bundles:
            raise ValueError(f"no evidence bundle for case {m.case_id!r}")
        out.append(
            AgentRunRecord.model_construct(
                run_id=f"run-RULES-{m.case_id}-r0",
                case_id=m.case_id,
                condition="RULES",
                model_id="rule-based",
                provider="none",
                prompt_hash="0" * 64,
                diagnosis=diagnose_by_rules(bundles[m.case_id]),
                patch_sha256=None,
                attempts=0,
                outcome="NO_PATCH",
                hidden_passed=None,
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                list_price_usd=0.0,
                latency_ms=0,
                tool_calls=0,
                invalid_tool_calls=0,
                cache_hits=0,
                dataset_sha256=dataset_sha256,
                git_sha=git_sha,
                replicate=0,
                temperature=None,
                seed=None,
                failure_reason=None,
            )
        )
    return out
