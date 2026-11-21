import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from traceforge.database import Base
from traceforge.repair.models import forbid_mutation


class Review(Base):
    """Insert-only. One review per incident (= per frozen patch)."""

    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("decision in ('approve','reject')", name="ck_reviews_decision"),
        UniqueConstraint("incident_id", name="uq_reviews_incident_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    patch_sha256: Mapped[str | None] = mapped_column(String(64))  # None for no-patch outcomes
    decision: Mapped[str] = mapped_column(String(16))
    reviewer: Mapped[str] = mapped_column(String(80))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


forbid_mutation(Review)
