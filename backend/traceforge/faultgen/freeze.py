"""Freeze the test split: `python -m traceforge.faultgen.freeze` (task dataset:freeze).

Writes, next to the manifests:
- test.sha256: SHA-256 of test.json (the experiment runner's freeze guard compares its first token).
- freeze.json: the freeze record: date, lab base_sha, counts, a content hash over every test case's
  files (patch, meta, reproducer, hidden tests) and the validation summary it was frozen on.
Refuses to freeze unless every test case passed validation in the given reports.
"""

import argparse
import collections
import glob
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from traceforge.faultgen import lab_tree


def content_sha256(datasets: Path, case_ids: list[str]) -> str:
    h = hashlib.sha256()
    for cid in sorted(case_ids):
        for sub in ("cases", "reproducers", "hidden_tests"):
            for p in (
                sorted((datasets / sub / cid).rglob("*")) if (datasets / sub / cid).is_dir() else []
            ):
                if p.is_file() and "__pycache__" not in p.parts:
                    rel = p.relative_to(datasets).as_posix()
                    h.update(rel.encode() + b"\0" + p.read_bytes().replace(b"\r\n", b"\n") + b"\n")
    return h.hexdigest()


def load_reports(pattern: str) -> list[dict]:
    rows = []
    for f in sorted(glob.glob(pattern)):
        split = Path(f).stem.split("-")[-1]
        for r in json.loads(Path(f).read_text("utf-8")):
            rows.append({**r, "split": split})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="traceforge.faultgen.freeze")
    ap.add_argument("--datasets", type=Path, default=lab_tree.datasets_dir())
    ap.add_argument(
        "--reports", default=str(lab_tree.repo_root() / "runs/validation/shard-*-*.json")
    )
    a = ap.parse_args(argv)
    man = a.datasets / "manifests"
    raw = (man / "test.json").read_bytes()
    cases = json.loads(raw)
    reports = load_reports(a.reports)
    by_id = {(r["split"], r["case_id"]): r for r in reports}
    missing = [c["case_id"] for c in cases if ("test", c["case_id"]) not in by_id]
    failed = [cid for (s, cid), r in by_id.items() if s == "test" and r.get("problems")]
    if missing or failed:
        print(f"refusing to freeze: {len(missing)} test cases not validated, {len(failed)} failed")
        return 1
    sha = hashlib.sha256(raw).hexdigest()
    (man / "test.sha256").write_text(f"{sha}  test.json\n", encoding="utf-8", newline="\n")
    lab = lab_tree.repo_root() / "lab"
    record = {
        "frozen_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "manifest": "test.json",
        "manifest_sha256": sha,
        "content_sha256": content_sha256(a.datasets, [c["case_id"] for c in cases]),
        "lab_base_sha": lab_tree.base_sha(lab),
        "cases": len(cases),
        "by_class": dict(collections.Counter(c["cause_class"] for c in cases)),
        "by_service": dict(collections.Counter(c["service"] for c in cases)),
        "variant_groups": len({c["variant_group"] for c in cases}),
        "fault_families": len({c["fault_family"] for c in cases}),
        "distance_ge_1": sum(1 for c in cases if (c["distance"] or 0) >= 1),
        "validation": {
            "runs_per_suite": 3,
            "reports": len(reports),
            "passed": sum(1 for r in reports if not r.get("problems")),
            "flaky_rejected": sum(
                1 for r in reports if any("flaky" in p for p in r.get("problems", []))
            ),
            "live_runtime_ok": sum(1 for r in reports if r["checks"].get("live_runtime") == "ok"),
        },
    }
    (man / "freeze.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    summary = [
        {k: r[k] for k in ("split", "case_id", "cause_class", "fault_family", "distance")}
        | {"passed": not r.get("problems"), "checks": r["checks"]}
        for r in sorted(reports, key=lambda r: (r["split"], r["case_id"]))
    ]
    (man / "validation.json").write_text(
        json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"frozen: test.json sha256={sha} ({len(cases)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
