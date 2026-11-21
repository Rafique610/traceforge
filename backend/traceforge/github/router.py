from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from traceforge.config import Settings, get_settings
from traceforge.database import get_db
from traceforge.github import service
from traceforge.github.client import GitHubError
from traceforge.github.schemas import GitHubIntake, GitHubIntakeOut

router = APIRouter(prefix="/incidents", tags=["github"])


@router.post("/from-github", status_code=201, response_model=GitHubIntakeOut)
def from_github(
    body: GitHubIntake,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return service.create_from_github(db, body, settings)
    except GitHubError as e:
        db.rollback()
        raise HTTPException(e.status, e.message) from None
