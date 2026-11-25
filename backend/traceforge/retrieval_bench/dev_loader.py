# ruff: noqa: E501
"""Loader that runs the registered methods on the TraceForge DEV split with the SAME harness.

Per repairable dev case that has a saved EvidenceBundle: the faulty tree is materialized (pristine
lab + the case's mutation patch, exactly as `retrieval.e1` does), the evidence is the pipeline-v5
bundle = saved evidence + visible-test symptom + deterministic diagnostics findings, rebuilt by
running ONLY the visible reproducer and visible suite on the base commit in the local sandbox
(approach of scripts/analysis_symptom_evidence.py). No hidden suite, no gold, no model. Gold
(manifest `gold_config_keys` + `gold_symbols`) goes to `BenchQuery.gold` for scoring only.
Refuses any manifest that is not the dev split (the frozen test split is never loaded here).
"""

from __future__ import annotations

import json
from pathlib import Path

from traceforge.contracts.case_manifest import REPAIRABLE
from traceforge.contracts.evidence import EvidenceBundle
from traceforge.evaluation.metrics.common import gold_node_ids
from traceforge.evaluation.runner import load_manifest
from traceforge.retrieval_bench.repo_ctx import build_context, query_text_from_evidence
from traceforge.retrieval_bench.suite import REPO_ROOT, Workload
from traceforge.retrieval_bench.types import BenchQuery, QueryText, norm_gold_id

DEV_MANIFEST = REPO_ROOT / "datasets" / "manifests" / "dev.json"


def _v5_evidence(case, datasets: Path, ev: EvidenceBundle, scratch: Path) -> EvidenceBundle:
    from traceforge.agent import symptom as sm
    from traceforge.agent.e2e import build_repo, rm_tree
    from traceforge.agent.real_sources import make_sandbox_run_tests
    from traceforge.repair.worktree import worktree

    repo_dir = scratch / f"sym-{case.case_id}"
    rm_tree(repo_dir)
    try:
        repo, head = build_repo(case, datasets, repo_dir)
        run = make_sandbox_run_tests(repo, datasets, case.service)
        with worktree(str(repo), head) as wt:
            sym = sm.collect_symptom(run, str(wt), case.case_id)
        return sm.with_symptom(ev, sym), sym.status
    finally:
        rm_tree(repo_dir)


def load_dev(
    manifest: Path = DEV_MANIFEST, evidence_dir: Path | None = None,
    trees_dir: Path | None = None, v5_dir: Path | None = None, rebuild_v5: bool = True,
    cases: list[str] | None = None,
) -> tuple[list[Workload], list[dict], dict]:  # fmt: skip
    """-> (workloads, skipped [{case_id, reason}], info). `v5_dir` caches rebuilt bundles."""
    evidence_dir = evidence_dir or REPO_ROOT / "runs" / "evidence"
    trees_dir = trees_dir or REPO_ROOT / "runs" / "bench_repos" / "dev_trees"
    v5_dir = v5_dir or REPO_ROOT / "runs" / "bench_repos" / "dev_evidence_v5"
    datasets = manifest.resolve().parents[1]
    ms, sha = load_manifest(manifest)
    if any(m.split != "dev" for m in ms) or "test" in manifest.name:
        raise ValueError("retrieval_bench loads the dev split only")
    from traceforge.faultgen.generate import materialize

    out: list[Workload] = []
    skipped: list[dict] = []
    v5_status: dict[str, str] = {}
    for m in sorted(ms, key=lambda c: c.case_id):
        if cases and m.case_id not in cases:
            continue
        if m.cause_class not in REPAIRABLE:
            skipped.append(
                {"case_id": m.case_id, "reason": f"no retrieval target ({m.cause_class})"}
            )
            continue
        ev_path = evidence_dir / f"{m.case_id}.json"
        if not ev_path.is_file():
            skipped.append({"case_id": m.case_id, "reason": "no saved EvidenceBundle"})
            continue
        v5_path = v5_dir / f"{m.case_id}.json"
        if v5_path.is_file():
            ev = EvidenceBundle.model_validate_json(v5_path.read_text("utf-8"))
            v5_status[m.case_id] = "cached"
        elif rebuild_v5:
            base = EvidenceBundle.model_validate_json(ev_path.read_text("utf-8"))
            try:
                ev, st = _v5_evidence(m, datasets, base, trees_dir.parent / "scratch")
            except Exception as e:  # sandbox unavailable: skip, never invent
                skipped.append(
                    {"case_id": m.case_id, "reason": f"v5 symptom rebuild failed: {e!r}"[:200]}
                )
                continue
            v5_dir.mkdir(parents=True, exist_ok=True)
            v5_path.write_text(ev.model_dump_json(indent=1), "utf-8")
            v5_status[m.case_id] = st
        else:
            skipped.append({"case_id": m.case_id, "reason": "no v5 evidence (rebuild disabled)"})
            continue
        patch = (datasets / "cases" / m.case_id / "mutation.patch").read_text("utf-8")
        tree = materialize(patch, trees_dir / m.case_id)
        ctx = build_context(m.case_id, tree)
        text = query_text_from_evidence(ctx.graph, ev, m.service)
        qt = QueryText(text, m.case_id, ev, m.service)
        gold = frozenset(norm_gold_id(g) for g in gold_node_ids(m))
        out.append(Workload("dev", ctx, [BenchQuery(m.case_id, m.cause_class, qt, gold)]))
    info = {"manifest": str(manifest), "dataset_sha256": sha, "n_cases": len(ms),
            "n_scored": len(out), "v5_symptom_status": v5_status}  # fmt: skip
    return out, skipped, info


def write_skipped(path: Path, skipped: list[dict]) -> None:
    path.write_text(json.dumps(skipped, indent=1), "utf-8")
