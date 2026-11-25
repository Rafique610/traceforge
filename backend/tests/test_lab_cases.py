"""GET /lab-cases lists investigable lab bugs; investigate says why others cannot run."""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from traceforge import investigation
from traceforge.config import Settings, get_settings
from traceforge.database import Base, get_db
from traceforge.incidents import models as _m  # noqa: F401
from traceforge.incidents import service
from traceforge.incidents.schemas import IncidentCreate


def _manifest(tmp_path):
    dev = Path(__file__).resolve().parents[2] / "datasets" / "manifests" / "dev.json"
    real = {c["case_id"]: c for c in json.loads(dev.read_text("utf-8"))}
    cases = [real["shop_api-002"], real["shop_api-056"], real["shop_api-001"]]
    m = tmp_path / "dev.json"
    m.write_text(json.dumps(cases), "utf-8")
    ev = tmp_path / "evidence"
    ev.mkdir()
    for c in ("shop_api-002", "shop_api-056"):  # 001 has no saved bundle here
        (ev / f"{c}.json").write_text("{}", "utf-8")
    return Settings(manifest=str(m), evidence_dir=ev)


def _client(settings):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def db():
        with sf() as s:
            yield s

    app = FastAPI()
    app.include_router(investigation.router)
    app.include_router(investigation.lab_cases_router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = db
    return TestClient(app), sf


def test_lists_only_cases_with_saved_evidence_and_hides_the_answer(tmp_path):
    client, _ = _client(_manifest(tmp_path))
    body = client.get("/lab-cases").json()
    assert body["configured"] is True
    assert body["cases"] == [
        {"case_id": "shop_api-002", "service": "shop_api"},
        {"case_id": "shop_api-056", "service": "worker"},
    ]


def test_no_manifest_means_not_configured(tmp_path):
    client, _ = _client(Settings(manifest=None, evidence_dir=tmp_path))
    assert client.get("/lab-cases").json() == {"configured": False, "cases": []}


def test_investigating_a_manual_incident_explains_why_not(tmp_path):
    client, sf = _client(_manifest(tmp_path))
    with sf() as s:
        iid = service.create_incident(s, IncidentCreate(service="shop_api", symptom="it fails")).id
    r = client.post(f"/incidents/{iid}/investigate")
    assert r.status_code == 422
    assert "not linked to a lab bug" in r.json()["detail"]


def test_case_without_saved_evidence_is_refused_with_a_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(investigation, "provider_ready", lambda s: True)
    settings = _manifest(tmp_path)
    inc = type("I", (), {"case_id": "shop_api-001"})()
    with pytest.raises(investigation.HTTPException) as e:
        investigation.InvestigationFactory().check(settings, inc)
    assert e.value.status_code == 422
    assert "no saved evidence" in e.value.detail
    investigation.InvestigationFactory().check(
        settings, type("I", (), {"case_id": "shop_api-002"})()
    )
