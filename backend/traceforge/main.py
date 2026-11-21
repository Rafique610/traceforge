from fastapi import FastAPI

from traceforge.config import get_settings
from traceforge.evaluation.analysis.router import router as evaluation_report_router
from traceforge.evaluation.router import router as evaluation_router
from traceforge.github.router import router as github_router
from traceforge.health.router import router as health_router
from traceforge.incidents.router import register_handlers as register_incident_handlers
from traceforge.incidents.router import router as incidents_router
from traceforge.reports.router import router as reports_router
from traceforge.reviews.router import register_handlers as register_review_handlers
from traceforge.reviews.router import router as reviews_router
from traceforge.showcase import add_showcase

app = FastAPI(title="TraceForge")
add_showcase(app, get_settings())
app.include_router(health_router)
app.include_router(incidents_router)
app.include_router(github_router)
app.include_router(reports_router)
app.include_router(reviews_router)
app.include_router(evaluation_router)
app.include_router(evaluation_report_router)
register_incident_handlers(app)
register_review_handlers(app)
