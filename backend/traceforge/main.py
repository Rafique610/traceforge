from fastapi import FastAPI

from traceforge.health.router import router as health_router

app = FastAPI(title="TraceForge")
app.include_router(health_router)
