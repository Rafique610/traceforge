"""Read-only GET /evaluation/report?run_ids=a&run_ids=b (orchestrator registers `router`).

The manifest is server-side config (`Settings.manifest`, env TRACEFORGE_MANIFEST); clients never
supply paths.
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import StringConstraints, ValidationError

from traceforge.config import Settings
from traceforge.evaluation import store
from traceforge.evaluation.analysis.report import DatasetMismatch, load_runs, report
from traceforge.evaluation.runner import load_manifest

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/report")
def get_report(
    run_ids: Annotated[
        list[Annotated[str, StringConstraints(pattern=store.RUN_ID_RE)]],
        Query(min_length=1, max_length=20),
    ],
) -> dict:
    manifest = Settings().manifest  # fresh read, like store.runs_dir()
    if not manifest:
        raise HTTPException(503, "TRACEFORGE_MANIFEST is not configured")
    try:
        manifests, sha = load_manifest(Path(manifest))
        records = load_runs(store.runs_dir(), run_ids)
        return report(records, manifests, manifest_sha256=sha)
    except OSError:
        raise HTTPException(404, "run or manifest not found") from None
    except DatasetMismatch as e:
        raise HTTPException(409, str(e)) from None
    except (ValueError, ValidationError) as e:
        raise HTTPException(422, str(e)[:500]) from None
