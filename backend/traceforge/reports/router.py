import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from traceforge.database import get_db
from traceforge.reports.builder import build_report
from traceforge.reports.render import render_markdown
from traceforge.reports.schemas import Report

router = APIRouter(prefix="/incidents", tags=["reports"])
Db = Annotated[Session, Depends(get_db)]


@router.get("/{incident_id}/report", response_model=Report)
def get_report(incident_id: uuid.UUID, db: Db, format: Literal["json", "md"] = "json"):
    report = build_report(db, incident_id)
    if report is None:
        raise HTTPException(404, "incident not found")
    if format == "md":
        return PlainTextResponse(render_markdown(report), media_type="text/markdown")
    return report
