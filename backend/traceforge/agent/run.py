"""CLI: python -m traceforge.agent.run [CASE|all] [--condition L0]; saves records to runs/dev/."""

import argparse
import json
from pathlib import Path

from traceforge.agent.pipeline import run_case, sample_sources
from traceforge.agent.sources import SAMPLES

SAMPLE_CASES = sorted(f.suffixes[0][1:] for f in SAMPLES.glob("case_manifest.*.json"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("case", nargs="?", default="all", help="sample name, case_id or 'all'")
    ap.add_argument("--condition", default="L0", choices=["L0", "G0", "L1", "G1"])
    ap.add_argument("--out", type=Path, default=Path("runs/dev"))
    args = ap.parse_args(argv)
    src = sample_sources()
    args.out.mkdir(parents=True, exist_ok=True)
    for name in SAMPLE_CASES if args.case == "all" else [args.case]:
        rec = run_case(src.cases.get(name), args.condition, src)
        text = rec.model_dump_json(indent=2)
        (args.out / f"{rec.run_id}.json").write_text(text, "utf-8")
        print(text)
        print(json.dumps({"saved": str(args.out / f"{rec.run_id}.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
