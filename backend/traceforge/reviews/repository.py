"""Reviews: add and read only."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from traceforge.reviews.models import Review


def add_review(db: Session, review: Review) -> Review:
    db.add(review)
    db.flush()
    return review


def get_review(db: Session, incident_id: uuid.UUID) -> Review | None:
    return db.scalars(select(Review).where(Review.incident_id == incident_id)).one_or_none()
