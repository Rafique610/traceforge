"""Markdown rendering of a Report. Pure string formatting."""

from traceforge.reports.schemas import Report


def _list(values: list[str]) -> str:
    return ", ".join(f"`{v}`" for v in values) or "none"


def render_markdown(r: Report) -> str:
    h = r.header
    out = [
        f"# Incident report {h.incident_id}",
        f"- Case: {h.case_id or '-'} | Service: {h.service or '-'} | Origin: {h.origin}",
        f"- Base SHA: {h.base_sha or '-'} | State: {h.state}",
        "",
        "## Symptom",
        r.symptom or "(none recorded)",
        f"Evidence: {_list(r.symptom_evidence_ids)}",
        "",
        "## Root cause",
        f"- Status: **{r.root_cause.status}** | Class: {r.root_cause.cause_class or '-'}"
        f" | Target: {r.root_cause.target or '-'}",
        f"- Evidence: {_list(r.root_cause.evidence_ids)}",
    ]
    o = r.outcome
    if o.dependency or o.dependency_evidence_ids:
        out.append(
            f"- Failing dependency: {o.dependency or '-'} ({_list(o.dependency_evidence_ids)})"
        )
    if r.root_cause.status == "INCONCLUSIVE":
        out.append("- Missing evidence: " + ("; ".join(o.missing_evidence) or "none listed"))
    out += ["", "## Evidence chain"]
    out += [
        f"- `{e.id}` {e.kind} {e.path or ''}:{e.line or ''} sha256 `{e.sha256}`" for e in r.evidence
    ]
    out += ["", "## Competing hypotheses"]
    out += [
        f"- {x.cause_class} {x.target or ''}: for {_list(x.supporting_ids)}; "
        f"against {_list(x.contradicting_ids)}"
        for x in r.hypotheses
    ] or ["none"]
    out += ["", "## Repair"]
    if r.patch:
        p = r.patch
        out += [
            f"- patch_sha256: `{p.sha256}`",
            f"- Changed paths: {_list(p.paths)}",
            f"- Signature changed: {'YES' if p.signature_changed else 'no'}",
        ]
        out += [
            f"- Impact of `{i.get('symbol')}`: {_list(i.get('impacted', []))}" for i in p.impact
        ]
        out += ["", "```diff", p.diff.rstrip("\n"), "```"]
    else:
        out.append("No patch.")
    out += ["", "## Validation runs"]
    out += [
        f"- attempt {v.attempt} {v.suite}: {v.passed} passed, {v.failed} failed ({v.outcome})"
        + "".join(f"\n  - `{t.get('id')}`: {t.get('outcome')}" for t in v.tests)
        for v in r.validation_runs
    ] or ["none"]
    out += ["", "## Model usage"]
    out.append(
        ", ".join(f"{k}: {v}" for k, v in sorted(r.model_usage.items()))
        if r.model_usage
        else "none"
    )
    out += ["", "## Reviewer decision"]
    rv = r.review
    out.append(
        f"{rv.decision} by {rv.reviewer} (patch `{rv.patch_sha256 or '-'}`): {rv.comment or ''}"
        if rv
        else "pending"
    )
    out += ["", "## Limitations", r.limitations, ""]
    return "\n".join(out)
