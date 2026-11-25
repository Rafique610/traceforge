"""Generate the committed fixture trees from templates.py + cases.py.

    python benchmarks/rootcause/build_fixtures.py            # (re)write cases/, CSV, derivations

Writes, per case, cases/<id>/case.json and either repo/ (families A-D, G, H: the BUGGY tree) or
base/ + patched/ (family F: clean tree and clean tree + patch). Also expected_relationships.csv
(for the second reviewer) and derivations.md. Output is byte-deterministic.
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cases import CASES, FAMILY_COUNTS  # noqa: E402
from templates import PROJECTS  # noqa: E402

OUT = HERE / "cases"


def apply_edits(files: dict[str, str], edits: list[tuple]) -> dict[str, str]:
    out = dict(files)
    for path, old, new in edits:
        if old is None:
            if path in out:
                raise ValueError(f"create over existing file {path}")
            out[path] = new
            continue
        if path not in out:
            raise ValueError(f"edit of missing file {path}")
        n = out[path].count(old)
        if n != 1:
            raise ValueError(f"{path}: expected exactly one match of {old!r}, found {n}")
        out[path] = out[path].replace(old, new)
    return out


def write_tree(root: Path, files: dict[str, str]) -> None:
    for rel, text in sorted(files.items()):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")


def _spec(case: dict) -> dict:
    spec = {k: v for k, v in case.items() if k != "edits"}
    spec["edits"] = [
        {"path": p, "kind": "create" if o is None else "replace", "old": o, "new": n}
        for p, o, n in case["edits"]
    ]
    spec["tree"] = {"base": "base", "patched": "patched"} if case["family"] == "F" else {"repo": "repo"}
    return spec


def csv_rows(case: dict) -> list[list[str]]:
    cid, fam = case["id"], case["family"]
    rows: list[list[str]] = []

    def add(rel: str, subj: str, obj: str = "") -> None:
        rows.append([cid, fam, rel, subj, obj, "", ""])

    if fam != "F":
        add("symptom_test", case["primary_test"])
        add("entry_point", case["entry"])
        ch = case["chain"]
        for a, b in zip(ch, ch[1:], strict=False):
            add("chain_step", a, b)
        for g in case["gold"]:
            add("acceptable_root_cause", g)
        for gf in case["gold_files"]:
            add("root_cause_file", gf)
        for d in case.get("extra_deps", []):
            add("expected_dependency", case["entry"], d)
        for d in case.get("decoys", []):
            add("decoy_not_root_cause", d)
        if case.get("abstain_expected"):
            add("expected_tool_behaviour", "abstain: dynamic call site next to the symptom")
    else:
        for m in case["modified"]:
            add("modified_symbol", m)
        for d in case["expected_dependants"]:
            add("expected_dependant", case["modified"][0], d)
        for d in case["expected_direct"]:
            add("expected_direct_dependant", case["modified"][0], d)
        for f in case["expected_flags"]:
            add("expected_risk_flag", f)
        for t in case["predicted_failing"]:
            add("predicted_failing_test", t)
    return rows


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    counts: dict[str, int] = {}
    rows: list[list[str]] = []
    md = ["# Derivations of expected relationships (hand-written)\n",
          "Written from the template source and the stated edit, before any tool run. "
          "Second reviewer: verify each row of `expected_relationships.csv` against these "
          "notes and the committed trees, and fill `reviewer_verdict` (ok / wrong / unclear).\n"]
    for case in CASES:
        counts[case["family"]] = counts.get(case["family"], 0) + 1
        base = PROJECTS[case["project"]]
        d = OUT / case["id"]
        buggy = apply_edits(base, case["edits"])
        if case["family"] == "F":
            write_tree(d / "base", base)
            write_tree(d / "patched", buggy)
        else:
            write_tree(d / "repo", buggy)
        (d / "case.json").write_text(json.dumps(_spec(case), indent=2, sort_keys=True) + "\n",
                                     encoding="utf-8", newline="\n")
        rows += csv_rows(case)
        md.append(f"\n## {case['id']} (family {case['family']}, project {case['project']}): "
                  f"{case['title']}\n\n{case['derivation']}\n")
    if counts != FAMILY_COUNTS:
        raise SystemExit(f"family counts {counts} != {FAMILY_COUNTS}")
    with (HERE / "expected_relationships.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["case_id", "family", "relation", "subject", "object",
                    "reviewer_verdict", "reviewer_note"])
        w.writerows(rows)
    (HERE / "derivations.md").write_text("".join(md), encoding="utf-8", newline="\n")
    print(f"{len(CASES)} cases, {len(rows)} relationship rows, families {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
