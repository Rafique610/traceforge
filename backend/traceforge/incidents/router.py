import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from traceforge.database import get_db
from traceforge.incidents import repository, service
from traceforge.incidents.schemas import (
    AuditEventOut,
    EvidenceItemOut,
    IncidentCreate,
    IncidentOut,
    IncidentPage,
)
from traceforge.incidents.states import State

router = APIRouter(prefix="/incidents", tags=["incidents"])
Db = Annotated[Session, Depends(get_db)]


def register_handlers(app: FastAPI) -> None:
    """Illegal transitions (raised by service.transition) become 409 with the current state."""

    @app.exception_handler(service.IllegalTransition)
    def _conflict(_: Request, exc: service.IllegalTransition) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc), "state": exc.current})


def _get_or_404(db: Session, incident_id: uuid.UUID):
    incident = repository.get_incident(db, incident_id)
    if incident is None:
        raise HTTPException(404, "incident not found")
    return incident


@router.post("", status_code=201, response_model=IncidentOut)
def create_incident(body: IncidentCreate, db: Db):
    return service.create_incident(db, body)


@router.get("", response_model=IncidentPage)
def list_incidents(
    db: Db,
    state: State | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = repository.list_incidents(db, state, limit, offset)
    return IncidentPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: uuid.UUID, db: Db):
    return _get_or_404(db, incident_id)


@router.get("/{incident_id}/events", response_model=list[AuditEventOut])
def get_events(incident_id: uuid.UUID, db: Db):
    _get_or_404(db, incident_id)
    return repository.list_events(db, incident_id)


@router.get("/{incident_id}/evidence", response_model=list[EvidenceItemOut])
def get_evidence(incident_id: uuid.UUID, db: Db):
    _get_or_404(db, incident_id)
    return repository.list_evidence(db, incident_id)
