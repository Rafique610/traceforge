"""Validate the dataset in N parallel shards (`python -m traceforge.faultgen.shards --shard K`).

Shard 1 owns every case with a live runtime check (they share one Docker compose project and must
not overlap); repairable cases are spread round-robin over all shards. Each shard writes
runs/validation/shard-K-<split>.json (the validator's own report) and a log next to it.
"""

import argparse
import json
import subprocess
import sys

from traceforge.faultgen import lab_tree

OUT = lab_tree.repo_root() / "runs" / "validation"


def plan(n: int) -> dict[int, dict[str, list[str]]]:
    shards: dict[int, dict[str, list[str]]] = {k: {"dev": [], "test": []} for k in range(1, n + 1)}
    i = 0
    for split in ("test", "dev"):
        rows = json.loads(
            (lab_tree.datasets_dir() / "manifests" / f"{split}.json").read_text("utf-8")
        )
        for c in sorted(rows, key=lambda c: c["case_id"]):
            if c["cause_class"] in ("runtime_dependency", "insufficient_evidence"):
                shards[1][split].append(c["case_id"])
            else:
                shards[(i % n) + 1][split].append(c["case_id"])
                i += 1
    return shards


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="traceforge.faultgen.shards")
    ap.add_argument("--shard", type=int, required=True)
    ap.add_argument("--of", type=int, default=4)
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    mine = plan(a.of)[a.shard]
    worst = 0
    for split, ids in mine.items():
        if not ids:
            continue
        args = [sys.executable, "-m", "traceforge.faultgen.validate", "--manifest", f"{split}.json",
                "--json", str(OUT / f"shard-{a.shard}-{split}.json")]  # fmt: skip
        for cid in ids:
            args += ["--case", cid]
        if a.shard != 1:
            args.append("--no-live")  # only shard 1 holds live runtime cases
        with open(OUT / f"shard-{a.shard}-{split}.log", "w", encoding="utf-8") as log:
            worst = max(
                worst, subprocess.run(args, stdout=log, stderr=subprocess.STDOUT).returncode
            )  # noqa: S603
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
