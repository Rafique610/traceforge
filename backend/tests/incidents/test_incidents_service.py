import hashlib
import inspect
import itertools

import pytest
from pydantic import ValidationError

from traceforge.contracts.evidence import EvidenceBundle, EvidenceItem
from traceforge.incidents import repository, service
from traceforge.incidents.models import Incident
from traceforge.incidents.schemas import IncidentCreate
from traceforge.incidents.service import IllegalTransition
from traceforge.incidents.states import ALLOWED, State

GOOD_PAYLOAD = {
    State.DIAGNOSED: {"evidence_ids": ["EV-0001"]},
    State.VERIFIED: {"repro_before": "failed", "repro_after": "passed"},
    State.REVIEWED: {"review_id": "RV-1"},
}


def make(db, state=State.CREATED) -> Incident:
    incident = service.create_incident(db, IncidentCreate(symptom="500s", service="api"))
    bundle = EvidenceBundle(
        incident_id=str(incident.id),
        base_sha="a" * 40,
        compose_sha256="b" * 64,
        items=[
            EvidenceItem(
                id="EV-0001",
                kind="log",
                service="api",
                content="boom",
                sha256=hashlib.sha256(b"x").hexdigest(),
            )
        ],
    )
    repository.save_evidence_bundle(db, bundle)
    incident.state = state
    db.commit()
    return incident


def n_events(db, incident) -> int:
    return len(repository.list_events(db, incident.id))


@pytest.mark.parametrize(
    ("frm", "to"), list(itertools.product(State, State)), ids=lambda s: s.value
)
def test_every_state_pair(db, frm, to):
    incident = make(db, frm)
    before = n_events(db, incident)
    if to in ALLOWED[frm]:
        service.transition(db, incident.id, to, "system", GOOD_PAYLOAD.get(to))
        assert incident.state is to
        events = repository.list_events(db, incident.id)
        assert len(events) == before + 1
        assert (events[-1].from_state, events[-1].to_state) == (frm, to)
    else:
        with pytest.raises(IllegalTransition):
            service.transition(db, incident.id, to, "system", GOOD_PAYLOAD.get(to))
        db.refresh(incident)
        assert incident.state is frm
        assert n_events(db, incident) == before


def test_allowed_map_covers_all_states_and_special_edges():
    assert set(ALLOWED) == set(State)
    assert State.REVIEW_PENDING in ALLOWED[State.DIAGNOSED]
    assert State.REVIEW_PENDING in ALLOWED[State.INCONCLUSIVE]
    assert ALLOWED[State.CLOSED] == set()


@pytest.mark.parametrize(
    ("frm", "to", "payload"),
    [
        (State.CONTEXT_RETRIEVED, State.DIAGNOSED, None),
        (State.CONTEXT_RETRIEVED, State.DIAGNOSED, {"evidence_ids": []}),
        (State.CONTEXT_RETRIEVED, State.DIAGNOSED, {"evidence_ids": ["EV-9999"]}),
        (State.VALIDATING, State.VERIFIED, None),
        (State.VALIDATING, State.VERIFIED, {"repro_before": "passed", "repro_after": "passed"}),
        (State.VALIDATING, State.VERIFIED, {"repro_before": "failed", "repro_after": "failed"}),
        (State.REVIEW_PENDING, State.REVIEWED, {}),
        (State.REVIEW_PENDING, State.REVIEWED, {"review_id": ""}),
    ],
)
def test_guards_reject_and_write_nothing(db, frm, to, payload):
    incident = make(db, frm)
    before = n_events(db, incident)
    with pytest.raises(IllegalTransition):
        service.transition(db, incident.id, to, "agent", payload)
    db.refresh(incident)
    assert incident.state is frm
    assert n_events(db, incident) == before


def test_audit_row_records_actor_payload_and_hash(db):
    incident = make(db, State.CONTEXT_RETRIEVED)
    payload = GOOD_PAYLOAD[State.DIAGNOSED]
    service.transition(db, incident.id, State.DIAGNOSED, "agent", payload)
    event = repository.list_events(db, incident.id)[-1]
    assert (event.actor, event.payload) == ("agent", payload)
    assert event.payload_sha256 == service._sha(payload)


def test_created_event_and_bad_actor_and_unknown_incident(db):
    incident = make(db)
    first = repository.list_events(db, incident.id)[0]
    assert (first.from_state, first.to_state, first.actor) == (None, State.CREATED, "system")
    with pytest.raises(ValueError):
        service.transition(db, incident.id, State.SNAPSHOT_LOCKED, "root")
    import uuid

    with pytest.raises(service.IncidentNotFound):
        service.transition(db, uuid.uuid4(), State.SNAPSHOT_LOCKED, "system")


def test_audit_is_append_only_in_repository_api():
    names = {n for n, f in inspect.getmembers(repository, inspect.isfunction)}
    assert "add_event" in names and "list_events" in names
    assert not [
        n
        for n in names
        if "event" in n and n.split("_")[0] in {"update", "delete", "remove", "edit"}
    ]


def test_create_schema_requires_case_or_symptom_and_service():
    IncidentCreate(case_id="c1")
    IncidentCreate(symptom="x", service="api")
    for bad in ({}, {"symptom": "x"}, {"service": "api"}):
        with pytest.raises(ValidationError):
            IncidentCreate(**bad)


def test_evidence_roundtrip_same_ev_id_across_incidents(db):
    a, b = make(db), make(db)  # both hold EV-0001
    assert [e.id for e in repository.list_evidence(db, a.id)] == ["EV-0001"]
    assert [e.id for e in repository.list_evidence(db, b.id)] == ["EV-0001"]
