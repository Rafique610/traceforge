from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from traceforge import __version__
from traceforge.database import get_db
from traceforge.health.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    """The app answers even when Postgres is down; `db` says which."""
    try:
        db.execute(select(1))
    except SQLAlchemyError:
        return HealthResponse(status="degraded", db="down", version=__version__)
    return HealthResponse(status="ok", db="up", version=__version__)
