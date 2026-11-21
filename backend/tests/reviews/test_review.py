import pytest
from sqlalchemy import select
from support import SHA, insufficient_incident, runtime_incident, verified_incident

from traceforge.incidents import repository as incidents
from traceforge.incidents.states import State
from traceforge.repair import repository as repair_repo
from traceforge.repair.models import Patch, ValidationRun
from traceforge.reviews import repository as review_repo
from traceforge.reviews.models import Review

OK = {"decision": "approve", "reviewer": "Rafique", "patch_sha256": SHA, "comment": "lgtm"}
NIL = "00000000-0000-0000-0000-000000000000"


def _post(client, inc, **over):
    return client.post(f"/incidents/{inc.id}/review", json={**OK, **over})


def test_approve_matching_hash_201_closes_and_audits(db, client):
    inc = verified_incident(db)
    res = _post(client, inc)
    assert res.status_code == 201 and res.json()["decision"] == "approve"
    db.expire_all()
    assert incidents.get_incident(db, inc.id).state is State.CLOSED
    events = incidents.list_events(db, inc.id)
    rev = next(e for e in events if e.to_state is State.REVIEWED)
    assert rev.actor == "reviewer:Rafique" and rev.payload["review_id"] == res.json()["id"]
    assert events[-1].to_state is State.CLOSED
    assert client.get(f"/incidents/{inc.id}/report").json()["review"]["reviewer"] == "Rafique"


def test_reject_is_stored_and_patch_untouched(db, client):
    inc = verified_incident(db)
    assert _post(client, inc, decision="reject").status_code == 201
    assert review_repo.get_review(db, inc.id).decision == "reject"
    assert repair_repo.get_patch(db, inc.id).diff.endswith("+x = 2\n")


def test_tampered_hash_409_nothing_stored(db, client):
    inc = verified_incident(db)
    bad = ("0" if SHA[0] != "0" else "1") + SHA[1:]
    assert _post(client, inc, patch_sha256=bad).status_code == 409
    db.expire_all()
    assert review_repo.get_review(db, inc.id) is None
    assert incidents.get_incident(db, inc.id).state is State.REVIEW_PENDING


def test_wrong_state_409(db, client):
    inc = verified_incident(db)
    incidents.get_incident(db, inc.id).state = State.VERIFIED
    db.commit()
    assert _post(client, inc).status_code == 409
    assert review_repo.get_review(db, inc.id) is None


def test_second_review_409(db, client):
    inc = verified_incident(db)
    assert _post(client, inc).status_code == 201
    assert _post(client, inc, decision="reject").status_code == 409


def test_missing_hash_when_patch_exists_422(db, client):
    inc = verified_incident(db)
    body = {k: v for k, v in OK.items() if k != "patch_sha256"}
    assert client.post(f"/incidents/{inc.id}/review", json=body).status_code == 422


def test_hash_given_without_patch_422(db, client):
    assert _post(client, runtime_incident(db)).status_code == 422


def test_no_patch_review_without_hash_ok(db, client):
    for make in (runtime_incident, insufficient_incident):
        inc = make(db)
        body = {k: v for k, v in OK.items() if k != "patch_sha256"}
        res = client.post(f"/incidents/{inc.id}/review", json=body)
        assert res.status_code == 201 and res.json()["patch_sha256"] is None


@pytest.mark.parametrize(
    "over",
    [
        {"decision": "maybe"},
        {"reviewer": ""},
        {"reviewer": "x" * 81},
        {"comment": "x" * 2001},
        {"patch_sha256": "abc"},
        {"patch_sha256": SHA.upper()},
    ],
)
def test_schema_constraints_422(db, client, over):
    assert _post(client, verified_incident(db), **over).status_code == 422


def test_unknown_incident_404(client):
    assert client.post(f"/incidents/{NIL}/review", json=OK).status_code == 404


def test_reviews_patches_runs_are_immutable(db, client):
    inc = verified_incident(db)
    _post(client, inc)
    for mod in (review_repo, repair_repo):
        assert not [n for n in dir(mod) if n.startswith(("update", "delete", "remove"))]
    attrs = {Review: "reviewer", ValidationRun: "outcome", Patch: "diff"}
    for model, attr in attrs.items():
        setattr(db.scalars(select(model)).first(), attr, "changed")
        with pytest.raises(RuntimeError):
            db.commit()
        db.rollback()
        db.delete(db.scalars(select(model)).first())
        with pytest.raises(RuntimeError):
            db.commit()
        db.rollback()
