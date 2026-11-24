"""Zero-token: build the pipeline-v5 symptom-augmented evidence (evidence + visible-test symptom +
deterministic diagnostics findings) for manifest cases, exactly as real_run v5 does before retrieval.
Runs only the visible reproducer + visible suite in the local sandbox on the faulty base commit
(no hidden suite, no gold, no model). Output: <out>/<case>.json (EvidenceBundle) + <out>/<case>.sym.json.
Run: backend/.venv/Scripts/python.exe scripts/analysis_symptom_evidence.py --manifest datasets/manifests/test.json \
        --evidence-dir <collected bundles> --out <dir> [--case ID ...] [--jobs N]
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from traceforge.agent import symptom as sm  # noqa: E402
from traceforge.agent.e2e import build_repo, rm_tree  # noqa: E402
from traceforge.agent.lab_collect import SCRATCH  # noqa: E402
from traceforge.agent.real_sources import make_sandbox_run_tests  # noqa: E402
from traceforge.contracts.case_manifest import CaseManifest  # noqa: E402
from traceforge.contracts.evidence import EvidenceBundle  # noqa: E402
from traceforge.repair.worktree import worktree  # noqa: E402


def one(case, datasets, ev_dir, out):
    f = out / f"{case.case_id}.json"
    if f.is_file():
        return case.case_id, "exists"
    t0 = time.monotonic()
    repo_dir = SCRATCH / "repos" / f"sym-{case.case_id}"
    rm_tree(repo_dir)
    try:
        repo, head = build_repo(case, datasets, repo_dir)
        run = make_sandbox_run_tests(repo, datasets, case.service)
        with worktree(str(repo), head) as wt:
            sym = sm.collect_symptom(run, str(wt), case.case_id)
        ev = EvidenceBundle.model_validate_json((ev_dir / f"{case.case_id}.json").read_text("utf-8"))
        v5 = sm.with_symptom(ev, sym)
        (out / f"{case.case_id}.sym.json").write_text(json.dumps(sym.as_dict(), indent=1), "utf-8")
        f.write_text(v5.model_dump_json(indent=1), "utf-8")
    finally:
        rm_tree(repo_dir)
    return case.case_id, f"{sym.status} {time.monotonic() - t0:.0f}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--evidence-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--case", action="append")
    ap.add_argument("--jobs", type=int, default=1)
    a = ap.parse_args()
    datasets = a.manifest.resolve().parents[1]
    cases = [CaseManifest.model_validate(r) for r in json.loads(a.manifest.read_text("utf-8"))]
    cases = [c for c in cases if not a.case or c.case_id in a.case]
    a.out.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(a.jobs) as ex:
        for cid, st in ex.map(lambda c: one(c, datasets, a.evidence_dir, a.out), cases):
            print(cid, st, flush=True)


if __name__ == "__main__":
    main()
