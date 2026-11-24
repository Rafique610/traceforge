# ruff: noqa: E501
import uuid
from types import SimpleNamespace

from traceforge import investigation
from traceforge.agent import symptom as symptom_mod


class _Inner:
    def collect(self, incident_id, service, case):
        return SimpleNamespace(items=["raw"])


class _Db:
    commits = 0

    def commit(self):
        self.commits += 1


def test_symptom_items_are_stored_before_the_pipeline_runs(monkeypatch):
    saved = []
    monkeypatch.setattr(investigation.repository, "list_evidence", lambda db, i: [])
    monkeypatch.setattr(
        investigation.repository, "save_evidence_bundle", lambda db, b: saved.append(b)
    )
    monkeypatch.setattr(
        symptom_mod, "with_symptom", lambda b, s: SimpleNamespace(items=[*b.items, "sym"])
    )
    db = _Db()
    src = investigation._SymptomPersistingEvidence(_Inner(), db, SimpleNamespace(status="ok"))
    out = src.collect(str(uuid.uuid4()), "svc", None)
    assert out.items == ["raw"]  # the pipeline still gets the raw bundle
    assert saved[0].items == ["raw", "sym"] and db.commits == 1


def test_blocked_symptom_stores_nothing(monkeypatch):
    saved = []
    monkeypatch.setattr(
        investigation.repository, "save_evidence_bundle", lambda db, b: saved.append(b)
    )
    src = investigation._SymptomPersistingEvidence(
        _Inner(), _Db(), SimpleNamespace(status="blocked: x")
    )
    src.collect(str(uuid.uuid4()), "svc", None)
    assert saved == []
