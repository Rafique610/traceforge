import ast
from pathlib import Path

from support import (
    SHA,
    insufficient_incident,
    runtime_incident,
    unverified_incident,
    verified_incident,
)

import traceforge.reports as reports_pkg
from traceforge.reports.builder import build_report
from traceforge.reports.render import render_markdown

NIL = "00000000-0000-0000-0000-000000000000"


def test_verified_report_has_patch_hash_impact_and_validation(db, client):
    inc = verified_incident(db)
    body = client.get(f"/incidents/{inc.id}/report").json()
    assert body["root_cause"]["status"] == "SUPPORTED"
    assert body["patch"]["sha256"] == SHA and "+x = 2" in body["patch"]["diff"]
    assert body["patch"]["signature_changed"] is True
    assert body["patch"]["impact"][0]["impacted"] == ["app.py::g"]
    assert [v["attempt"] for v in body["validation_runs"]] == [0, 1]
    assert body["review"] is None


def test_unverified_report_with_patch_and_no_runs(db, client):
    inc = unverified_incident(db)
    body = client.get(f"/incidents/{inc.id}/report").json()
    assert body["root_cause"]["cause_class"] == "configuration"
    assert body["validation_runs"] == [] and body["patch"]["sha256"] == SHA


def test_runtime_dependency_names_dependency_and_evidence(db, client):
    inc = runtime_incident(db)
    body = client.get(f"/incidents/{inc.id}/report").json()
    assert body["root_cause"]["status"] == "RUNTIME_DEPENDENCY"
    assert body["outcome"]["dependency"] == "redis"
    assert body["outcome"]["dependency_evidence_ids"] == ["EV-0001"]
    assert body["patch"] is None


def test_insufficient_evidence_lists_missing(db, client):
    inc = insufficient_incident(db)
    body = client.get(f"/incidents/{inc.id}/report").json()
    assert body["root_cause"]["status"] == "INCONCLUSIVE"
    assert body["outcome"]["missing_evidence"] == ["worker logs", "db metrics"]
    md = client.get(f"/incidents/{inc.id}/report?format=md").text
    assert "Missing evidence: worker logs; db metrics" in md


def test_every_id_resolves(db):
    r = build_report(db, verified_incident(db).id)
    known = {e.id for e in r.evidence}
    assert known == {"EV-0001"}
    assert set(r.root_cause.evidence_ids) <= known
    assert set(r.symptom_evidence_ids) <= known


def test_markdown_format(db, client):
    inc = verified_incident(db)
    res = client.get(f"/incidents/{inc.id}/report?format=md")
    assert res.headers["content-type"].startswith("text/markdown")
    assert SHA in res.text and "```diff" in res.text and "Signature changed: YES" in res.text
    assert res.text == render_markdown(build_report(db, inc.id))


def test_report_404_and_bad_format(client):
    assert client.get(f"/incidents/{NIL}/report").status_code == 404
    assert client.get(f"/incidents/{NIL}/report?format=x").status_code == 422


def test_report_code_never_touches_llm_or_network():
    banned = (
        "traceforge.agent",
        "httpx",
        "requests",
        "openai",
        "anthropic",
        "socket",
        "subprocess",
    )
    for f in Path(reports_pkg.__file__).parent.glob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            assert not [m for m in mods if m.startswith(banned)], (f.name, mods)


def test_report_is_deterministic(db):
    inc = verified_incident(db)
    assert build_report(db, inc.id) == build_report(db, inc.id)


def test_incident_without_diagnosis_is_not_reported_as_supported(db, client):
    """Found in the live UI walkthrough: a CREATED incident showed 'SUPPORTED'."""
    from traceforge.incidents.schemas import IncidentCreate
    from traceforge.incidents.service import create_incident

    inc = create_incident(db, IncidentCreate(symptom="boom", service="shop_api"))
    body = client.get(f"/incidents/{inc.id}/report").json()
    assert body["root_cause"]["status"] == "NOT_DIAGNOSED"
    assert body["root_cause"]["evidence_ids"] == []


def test_unverified_repairable_incident_is_not_labelled_verified(db, client):
    """Found in the real end-to-end run: a misdiagnosis carried the 'verified' caveat."""
    inc = unverified_incident(db)
    body = client.get(f"/incidents/{inc.id}/report").json()
    assert "NOT verified" in body["limitations"]
    assert "Verified only by" not in body["limitations"]


def test_verified_incident_keeps_the_verified_caveat(db, client):
    inc = verified_incident(db)
    body = client.get(f"/incidents/{inc.id}/report").json()
    assert body["limitations"].startswith("Verified only by")


def test_missing_evidence_event_from_the_pipeline_reaches_the_report(client, db):
    from support import PRE, make_incident

    from traceforge.agent.persist import record_missing_evidence
    from traceforge.contracts.evidence import EvidenceBundle
    from traceforge.incidents.states import State

    inc = make_incident(db, cause="insufficient_evidence", path=[*PRE, State.INCONCLUSIVE])
    bundle = EvidenceBundle(
        incident_id=str(inc.id), base_sha="a" * 40, compose_sha256="b" * 64, items=[]
    )
    record_missing_evidence(db, inc, bundle, "insufficient_evidence")
    body = client.get(f"/incidents/{inc.id}/report").json()
    assert any("log" in m for m in body["outcome"]["missing_evidence"])
