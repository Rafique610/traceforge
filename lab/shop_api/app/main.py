"""App factory: wires routers and health endpoints."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import health
from app.db import get_engine, get_session
from app.models import Base
from app.queue import OrderQueue, get_queue
from app.routes import orders, products

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(get_engine())  # lab-only: no migrations
    yield


logger = logging.getLogger("app.main")
app = FastAPI(title="Lab shop API", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def log_validation_error(request: Request, exc: RequestValidationError):
    """Log which field was rejected (message text only, never the input), keep FastAPI's 422 body."""
    details = "; ".join(
        f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()
    )
    logger.warning(
        "validation error on %s %s: %s", request.method, request.url.path, details
    )
    return JSONResponse(
        status_code=422, content={"detail": jsonable_encoder(exc.errors())}
    )


app.include_router(products.router)
app.include_router(orders.router)


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health")
def health_check(
    session: Session = Depends(get_session), queue: OrderQueue = Depends(get_queue)
):
    parts = {
        "db": health.check_db(session),
        "redis": health.check_redis(queue),
        "worker": health.check_worker(queue),
    }
    ok = all(v == "ok" for v in parts.values())
    return JSONResponse(
        {"status": "ok" if ok else "degraded", **parts}, status_code=200 if ok else 503
    )
