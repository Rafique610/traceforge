"""Run store: runs/<run_id>/{meta.json,records/<case_id>.r<k>.json}. Read helpers for the API."""

import json
import os
from collections import Counter
from pathlib import Path

from traceforge.config import Settings
from traceforge.contracts.agent_run import AgentRunRecord

RUN_ID_RE = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$"


def runs_dir() -> Path:
    """Read fresh (not the cached settings) so a changed TRACEFORGE_RUNS_DIR applies at once."""
    return Settings().runs_dir


def record_path(run_dir: Path, case_id: str, replicate: int) -> Path:
    return run_dir / "records" / f"{case_id}.r{replicate}.json"


def write_json(path: Path, text: str) -> None:
    """Atomic write so an interrupt never leaves a half-written record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def has_record(run_dir: Path, case_id: str, replicate: int) -> bool:
    p = record_path(run_dir, case_id, replicate)
    try:
        AgentRunRecord.model_validate_json(p.read_text("utf-8"))
        return True
    except (OSError, ValueError):
        return False


def read_records(run_dir: Path) -> list[AgentRunRecord]:
    return [
        AgentRunRecord.model_validate_json(p.read_text("utf-8"))
        for p in sorted((run_dir / "records").glob("*.json"))
    ]


def load_run(runs: Path, run_id: str) -> dict:
    """Raw counts only: n_records vs n_expected, outcomes. No metrics (those are Rafique's)."""
    d = runs / run_id
    meta = json.loads((d / "meta.json").read_text("utf-8"))
    recs = read_records(d)
    return {
        "run_id": run_id,
        "meta": meta,
        "n_records": len(recs),
        "n_expected": meta.get("n_expected"),
        "complete": meta.get("finished_at") is not None and len(recs) == meta.get("n_expected"),
        "outcome_counts": dict(Counter(r.outcome for r in recs)),
        "failure_reason_counts": dict(Counter(r.failure_reason for r in recs if r.failure_reason)),
        "records": [r.model_dump() for r in recs],
    }


def list_runs(runs: Path) -> list[dict]:
    out = []
    for m in sorted(runs.glob("*/meta.json")) if runs.is_dir() else []:
        try:
            s = load_run(runs, m.parent.name)
        except (OSError, ValueError):
            continue
        s.pop("records")
        out.append(s)
    return out


_ROW = ("case_id", "replicate", "outcome", "attempts", "hidden_passed", "failure_reason")


def page_records(runs: Path, run_id: str, limit: int, offset: int) -> dict:
    """Per-case rows (raw fields only), sorted by case_id then replicate."""
    (runs / run_id / "meta.json").stat()  # OSError -> 404 for unknown runs
    recs = read_records(runs / run_id)
    recs.sort(key=lambda r: (r.case_id, r.replicate))
    rows = [
        {
            **{k: getattr(r, k) for k in _ROW},
            "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out,
            "latency_ms": r.latency_ms,
            "condition": r.condition,
            "pipeline_version": r.pipeline_version,
            "diagnosis": {
                "cause_class": r.diagnosis.cause_class,
                "target": r.diagnosis.target,
                "abstained": r.diagnosis.abstained,
            },
        }
        for r in recs[offset : offset + limit]
    ]
    return {"items": rows, "total": len(recs), "limit": limit, "offset": offset}
