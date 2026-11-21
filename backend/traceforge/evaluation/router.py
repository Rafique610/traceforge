"""Read-only run listing: raw counts, no computed metrics."""

from fastapi import APIRouter, HTTPException, Path, Query

from traceforge.evaluation import store

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/runs")
def get_runs() -> list[dict]:
    return store.list_runs(store.runs_dir())


@router.get("/runs/{run_id}")
def get_run(run_id: str = Path(pattern=store.RUN_ID_RE)) -> dict:
    try:
        return store.load_run(store.runs_dir(), run_id)
    except OSError:
        raise HTTPException(404, "run not found") from None


@router.get("/runs/{run_id}/records")
def get_run_records(
    run_id: str = Path(pattern=store.RUN_ID_RE),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    try:
        return store.page_records(store.runs_dir(), run_id, limit, offset)
    except OSError:
        raise HTTPException(404, "run not found") from None
