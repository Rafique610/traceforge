"""`report(records, manifests, contexts=None) -> dict`: every number recomputed from saved records.

Shape: {dataset, n_records, n_cases, conditions: {C: {overall, breakdowns}},
retrieval: {mode: ...}, paired: [...], not_available: [...]}. Every ratio is {num, den, value}.

CLI: python -m traceforge.evaluation.analysis.report --runs-dir runs --manifest m.json
     [--run-id ID ...] [--out report.json]
"""

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path

from traceforge.contracts.agent_run import AgentRunRecord
from traceforge.contracts.case_manifest import CaseManifest
from traceforge.contracts.context import ContextBundle
from traceforge.evaluation import store
from traceforge.evaluation.metrics import condition_section
from traceforge.evaluation.metrics.common import group_by, join
from traceforge.evaluation.metrics.paired import all_paired
from traceforge.evaluation.metrics.retrieval import retrieval_report

NOT_AVAILABLE = [
    "invalid-edit rate, lines changed per patch, new ruff errors, parse failures and "
    "signature-change rate: AgentRunRecord does not store them (failure_reason codes are "
    "broken down under repair.failure_reasons instead)",
    "cache_hit_rate is cache_hits / tool_calls; the record does not say what a hit counts",
]


class DatasetMismatch(ValueError):
    """Records were produced against a different dataset than the manifest: refuse to score."""


def check_dataset(records: list[AgentRunRecord], manifest_sha256: str | None) -> dict:
    found = sorted({r.dataset_sha256 for r in records})
    if manifest_sha256 is not None:
        bad = [s for s in found if s != manifest_sha256]
        if bad:
            raise DatasetMismatch(
                f"record dataset_sha256 {bad} differs from manifest sha256 {manifest_sha256}"
            )
        return {"sha256": manifest_sha256, "verified_against_manifest": True}
    if len(found) > 1:
        raise DatasetMismatch(f"records span several datasets: {found}")
    return {"sha256": found[0] if found else None, "verified_against_manifest": False}


def report(
    records: Iterable[AgentRunRecord],
    manifests: Iterable[CaseManifest],
    contexts: Iterable[ContextBundle] | None = None,
    *,
    manifest_sha256: str | None = None,
    bootstrap_iterations: int = 10_000,
    seed: int = 0,
) -> dict:
    records, manifests = list(records), list(manifests)
    dataset = check_dataset(records, manifest_sha256)
    pairs = join(records, manifests)
    out: dict = {
        "dataset": dataset,
        "n_records": len(pairs),
        "n_cases": len({r.case_id for r, _ in pairs}),
        "n_manifest_cases": len(manifests),
        "conditions": {
            c: condition_section(v) for c, v in group_by(pairs, lambda p: p[0].condition).items()
        },
        "paired": all_paired(pairs, bootstrap_iterations, seed),
        "not_available": NOT_AVAILABLE,
    }
    if contexts is not None:
        by_id = {m.case_id: m for m in manifests}
        items = []
        for b in contexts:
            if b.incident_id not in by_id:
                raise ValueError(f"context for unknown case {b.incident_id!r}")
            items.append((b, by_id[b.incident_id]))
        out["retrieval"] = retrieval_report(items)
    return out


def load_runs(runs_dir: Path, run_ids: list[str] | None = None) -> list[AgentRunRecord]:
    """Records of the named runs (default: every run); an unknown run id raises OSError."""
    ids = run_ids or [m.parent.name for m in sorted(runs_dir.glob("*/meta.json"))]
    recs: list[AgentRunRecord] = []
    for i in ids:
        (runs_dir / i / "meta.json").stat()
        recs.extend(store.read_records(runs_dir / i))
    return recs


def main(argv: list[str] | None = None) -> int:
    from traceforge.evaluation.runner import load_manifest

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs-dir", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--run-id", action="append", help="repeatable; default all runs")
    ap.add_argument("--out", type=Path, help="write report JSON here (default stdout)")
    a = ap.parse_args(argv)
    manifests, sha = load_manifest(a.manifest)
    try:
        rep = report(load_runs(a.runs_dir, a.run_id), manifests, manifest_sha256=sha)
    except (DatasetMismatch, ValueError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    text = json.dumps(rep, indent=2, sort_keys=True)
    if a.out:
        a.out.write_text(text, "utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
