"""Hash-bound review. Nothing here applies or deploys a patch, whatever the decision."""

import hashlib
import uuid

from sqlalchemy.orm import Session

from traceforge.incidents import repository as incidents
from traceforge.incidents import service as lifecycle
from traceforge.incidents.states import State
from traceforge.repair import repository as patches
from traceforge.reviews import repository
from traceforge.reviews.models import Review
from traceforge.reviews.schemas import ReviewCreate


class ReviewInvalid(Exception):
    """Request does not fit the incident (hash missing, or given without a patch). HTTP 422."""


def _check(db: Session, incident_id: uuid.UUID, state: State, data: ReviewCreate) -> None:
    if state is not State.REVIEW_PENDING:
        raise lifecycle.IllegalTransition(state, State.REVIEWED, "review requires REVIEW_PENDING")
    patch = patches.get_patch(db, incident_id)
    if patch is None and data.patch_sha256 is not None:
        raise ReviewInvalid("incident has no frozen patch; omit patch_sha256")
    if patch is not None:
        if data.patch_sha256 is None:
            raise ReviewInvalid("patch_sha256 is required for this incident")
        if hashlib.sha256(patch.diff.encode()).hexdigest() != patch.sha256:
            raise lifecycle.IllegalTransition(
                state,
                State.REVIEWED,
                "frozen patch is corrupt: stored diff does not match its hash",
            )
        if data.patch_sha256 != patch.sha256:
            raise lifecycle.IllegalTransition(
                state, State.REVIEWED, "patch hash does not match the frozen patch"
            )
        if data.decision == "approve":
            events = incidents.list_events(db, incident_id)
            if not any(e.to_state is State.VERIFIED for e in events):
                raise lifecycle.IllegalTransition(
                    state, State.REVIEWED, "only a VERIFIED patch can be approved"
                )


def submit_review(db: Session, incident_id: uuid.UUID, data: ReviewCreate) -> Review:
    incident = incidents.get_incident(db, incident_id, lock=True)
    if incident is None:
        db.rollback()
        raise lifecycle.IncidentNotFound(str(incident_id))
    try:
        _check(db, incident_id, incident.state, data)
    except Exception:
        db.rollback()  # nothing stored; releases the row lock
        raise
    review = repository.add_review(
        db,
        Review(
            incident_id=incident_id,
            patch_sha256=data.patch_sha256,
            decision=data.decision,
            reviewer=data.reviewer,
            comment=data.comment,
        ),
    )
    # The first transition commits the review row and its audit event in one transaction.
    lifecycle.transition(
        db,
        incident_id,
        State.REVIEWED,
        f"reviewer:{data.reviewer}",
        {"review_id": str(review.id), "decision": data.decision, "patch_sha256": data.patch_sha256},
    )
    lifecycle.transition(db, incident_id, State.CLOSED, "system", {"review_id": str(review.id)})
    return review
