import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from traceforge.database import get_db
from traceforge.incidents.service import IncidentNotFound
from traceforge.reviews import service
from traceforge.reviews.schemas import ReviewCreate, ReviewOut

router = APIRouter(prefix="/incidents", tags=["reviews"])
Db = Annotated[Session, Depends(get_db)]


def register_handlers(app: FastAPI) -> None:
    """422 for unusable hash input. IllegalTransition (409) is registered by incidents."""

    @app.exception_handler(service.ReviewInvalid)
    def _invalid(_: Request, exc: service.ReviewInvalid) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})


@router.post("/{incident_id}/review", status_code=201, response_model=ReviewOut)
def create_review(incident_id: uuid.UUID, body: ReviewCreate, db: Db):
    try:
        return service.submit_review(db, incident_id, body)
    except IncidentNotFound:
        raise HTTPException(404, "incident not found") from None
