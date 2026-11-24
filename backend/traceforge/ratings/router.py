import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from traceforge.database import get_db
from traceforge.ratings import service
from traceforge.ratings.schemas import RatingIn, RatingOut, RatingSummary

router = APIRouter(tags=["ratings"])
Db = Annotated[Session, Depends(get_db)]


@router.post("/incidents/{incident_id}/ratings", status_code=201, response_model=RatingOut)
def create_rating(incident_id: uuid.UUID, body: RatingIn, db: Db):
    try:
        return service.save(db, incident_id, body)
    except service.NoReport:
        raise HTTPException(404, "incident or report not found") from None


@router.get("/ratings/summary", response_model=RatingSummary)
def get_summary():
    return service.summarize(service.load_all())
