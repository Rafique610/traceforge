import json

import pytest

from traceforge.ratings import service

GOOD = {
    "rater": "ruhan",
    "cause_clear": 4,
    "evidence_convincing": 5,
    "patch_understandable": 3,
    "would_approve": 4,
    "note": "clear",
}


@pytest.fixture(autouse=True)
def _dir(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "ratings_dir", lambda: tmp_path / "ratings")
    return tmp_path / "ratings"


def _incident(client) -> str:
    return client.post("/incidents", json={"symptom": "checkout 500", "service": "api"}).json()[
        "id"
    ]


def test_rating_saved_with_report_hash(client, _dir):
    iid = _incident(client)
    r = client.post(f"/incidents/{iid}/ratings", json=GOOD)
    assert r.status_code == 201
    saved = json.loads(next(_dir.glob("*.json")).read_text("utf-8"))
    assert saved["incident_id"] == iid and len(saved["report_sha256"]) == 64
    assert saved["would_approve"] == 4


def test_hash_changes_when_report_changes(client, db):
    import uuid

    from traceforge.incidents import service as incidents

    iid = _incident(client)
    h1 = service.report_hash(db, uuid.UUID(iid))
    incidents.transition(db, uuid.UUID(iid), incidents.State.SNAPSHOT_LOCKED, "system")
    assert service.report_hash(db, uuid.UUID(iid)) != h1


@pytest.mark.parametrize("field,value", [("cause_clear", 0), ("would_approve", 6), ("rater", "")])
def test_invalid_rating_rejected_nothing_written(client, _dir, field, value):
    iid = _incident(client)
    assert client.post(f"/incidents/{iid}/ratings", json={**GOOD, field: value}).status_code == 422
    assert not _dir.exists() or not list(_dir.glob("*.json"))


def test_unknown_incident_404(client):
    assert (
        client.post(
            f"/incidents/{'0' * 8}-0000-0000-0000-{'0' * 12}/ratings", json=GOOD
        ).status_code
        == 404
    )


def test_summary_means(client):
    iid = _incident(client)
    client.post(f"/incidents/{iid}/ratings", json=GOOD)
    client.post(f"/incidents/{iid}/ratings", json={**GOOD, "cause_clear": 2})
    s = client.get("/ratings/summary").json()
    assert s["n"] == 2 and s["mean"]["cause_clear"] == 3.0


def test_summary_empty(client):
    assert client.get("/ratings/summary").json() == {
        "n": 0,
        "mean": {q: None for q in service.QUESTIONS},
    }
