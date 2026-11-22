import uuid
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from traceforge.database import get_db
from traceforge.incidents import service
from traceforge.incidents.router import register_handlers
from traceforge.incidents.states import State
from traceforge.main import app

BODY = {"symptom": "checkout returns 500", "service": "api"}


def test_create_get_events(client):
    r = client.post("/incidents", json=BODY)
    assert r.status_code == 201
    inc = r.json()
    assert (inc["state"], inc["source"]) == ("CREATED", "manual")
    got = client.get(f"/incidents/{inc['id']}").json()  # SQLite drops tz; compare stable fields
    assert (got["id"], got["state"], got["symptom"]) == (inc["id"], "CREATED", BODY["symptom"])
    events = client.get(f"/incidents/{inc['id']}/events").json()
    assert [(e["from_state"], e["to_state"]) for e in events] == [(None, "CREATED")]
    assert client.get(f"/incidents/{inc['id']}/evidence").json() == []


def test_create_with_case_id_only_is_lab_case(client):
    r = client.post("/incidents", json={"case_id": "case-001"})
    assert r.status_code == 201 and r.json()["source"] == "lab_case"


def test_create_validation_422(client):
    assert client.post("/incidents", json={}).status_code == 422
    assert client.post("/incidents", json={"symptom": "x"}).status_code == 422
    assert client.post("/incidents", json={**BODY, "source": "bogus"}).status_code == 422


def test_unknown_incident_404_and_bad_uuid_422(client):
    missing = uuid.uuid4()
    for suffix in ("", "/events", "/evidence"):
        assert client.get(f"/incidents/{missing}{suffix}").status_code == 404
    assert client.get("/incidents/not-a-uuid").status_code == 422


def test_list_filter_and_pagination(client, session_factory):
    ids = [client.post("/incidents", json=BODY).json()["id"] for _ in range(5)]
    with session_factory() as db:
        service.transition(db, uuid.UUID(ids[0]), State.SNAPSHOT_LOCKED, "system")
    page = client.get("/incidents", params={"limit": 2, "offset": 0}).json()
    assert (page["total"], len(page["items"]), page["limit"]) == (5, 2, 2)
    seen = {i["id"] for i in page["items"]}
    page2 = client.get("/incidents", params={"limit": 2, "offset": 2}).json()
    page3 = client.get("/incidents", params={"limit": 2, "offset": 4}).json()
    seen |= {i["id"] for i in page2["items"]} | {i["id"] for i in page3["items"]}
    assert seen == set(ids) and len(page3["items"]) == 1
    locked = client.get("/incidents", params={"state": "SNAPSHOT_LOCKED"}).json()
    assert (locked["total"], locked["items"][0]["id"]) == (1, ids[0])
    assert client.get("/incidents", params={"state": "NOPE"}).status_code == 422
    assert client.get("/incidents", params={"limit": 0}).status_code == 422
    assert client.get("/incidents", params={"limit": 101}).status_code == 422


def test_illegal_transition_maps_to_409_and_writes_nothing(client):
    # No public transition endpoint exists yet; a throwaway app proves the 409 mapping.
    mini = FastAPI()
    register_handlers(mini)
    mini.dependency_overrides = app.dependency_overrides

    @mini.post("/t/{incident_id}/{to}")
    def _t(incident_id: uuid.UUID, to: State, db: Annotated[Session, Depends(get_db)]):
        service.transition(db, incident_id, to, "system", {})
        return {}

    t = TestClient(mini)
    inc = client.post("/incidents", json=BODY).json()
    events = f"/incidents/{inc['id']}/events"
    r = t.post(f"/t/{inc['id']}/VERIFIED")
    assert r.status_code == 409 and r.json()["state"] == "CREATED"
    assert t.post(f"/t/{inc['id']}/SNAPSHOT_LOCKED").status_code == 200
    assert len(client.get(events).json()) == 2
    assert t.post(f"/t/{inc['id']}/DIAGNOSED").status_code == 409
    assert len(client.get(events).json()) == 2


def test_unknown_case_id_is_422_when_manifest_configured(client, monkeypatch, tmp_path):
    from traceforge import config
    from traceforge.incidents import router

    manifest = tmp_path / "m.json"
    manifest.write_text('[{"case_id": "shop_api-001"}]', encoding="utf-8")
    monkeypatch.setattr(router, "get_settings", lambda: config.Settings(manifest=str(manifest)))
    assert client.post("/incidents", json={"case_id": "nope-9"}).status_code == 422
    assert client.post("/incidents", json={"case_id": "shop_api-001"}).status_code == 201
    assert client.get("/incidents").json()["total"] == 1  # nothing written for the rejected one
