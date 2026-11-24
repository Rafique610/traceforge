"""Ratings are saved as JSON files that carry the hash of the exact report that was rated."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from traceforge.config import get_settings
from traceforge.ratings.schemas import RatingIn, RatingOut, RatingSummary
from traceforge.reports.builder import build_report

QUESTIONS = ("cause_clear", "evidence_convincing", "patch_understandable", "would_approve")


class NoReport(LookupError):
    """The incident does not exist or has no report yet."""


def ratings_dir() -> Path:
    return get_settings().ratings_dir


def report_hash(db: Session, incident_id: uuid.UUID) -> str:
    report = build_report(db, incident_id)
    if report is None:
        raise NoReport(str(incident_id))
    canonical = json.dumps(report.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def save(db: Session, incident_id: uuid.UUID, body: RatingIn) -> RatingOut:
    out = RatingOut(
        **body.model_dump(),
        incident_id=str(incident_id),
        report_sha256=report_hash(db, incident_id),
        created_at=datetime.now(UTC).isoformat(),
    )
    directory = ratings_dir()
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{incident_id}-{uuid.uuid4().hex[:8]}.json"
    (directory / name).write_text(out.model_dump_json(indent=2), encoding="utf-8")
    return out


def load_all() -> list[RatingOut]:
    directory = ratings_dir()
    if not directory.exists():
        return []
    return [
        RatingOut.model_validate_json(p.read_text("utf-8"))
        for p in sorted(directory.glob("*.json"))
    ]


def summarize(ratings: list[RatingOut]) -> RatingSummary:
    n = len(ratings)
    mean = {q: (sum(getattr(r, q) for r in ratings) / n if n else None) for q in QUESTIONS}
    return RatingSummary(n=n, mean=mean)
