# ruff: noqa: E501
"""Generate cases: `python -m traceforge.faultgen.generate [--tree-out DIR --case ID]`.

Writes, per case: datasets/cases/<id>/{mutation.patch,runtime.yaml,meta.json} (generator side, never
model-visible), datasets/reproducers/<id>/ (visible), datasets/hidden_tests/<id>/ (hidden), and
datasets/manifests/dev.json (JSON list of CaseManifest, split "dev").
"""

import argparse
import json
import shutil
from pathlib import Path

from traceforge.faultgen import lab_tree
from traceforge.faultgen.model import BuiltCase, CaseDraft, build_case
from traceforge.faultgen.patching import apply_patch
from traceforge.faultgen.seeds import seed_drafts


def _yaml(data: dict) -> str:
    out = []
    for key, val in data.items():
        if isinstance(val, list):
            out.append(f"{key}:")
            out += [f"  - {v}" for v in val]
        else:
            out.append(f"{key}: {val}")
    return "\n".join(out) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))  # LF always


def write_case(built: BuiltCase, datasets: Path) -> None:
    d: CaseDraft = built.draft
    cid = d.case_id
    for sub in ("cases", "reproducers", "hidden_tests"):
        shutil.rmtree(datasets / sub / cid, ignore_errors=True)
    _write(datasets / "cases" / cid / "mutation.patch", built.patch)
    if d.runtime:
        _write(datasets / "cases" / cid / "runtime.yaml", _yaml(d.runtime))
    meta = {
        "template": d.template,
        "params": d.params,
        "distance_source": d.distance_source,
        "base_sha": built.manifest.base_sha,
        "runtime": d.runtime,
        "notes": d.notes,
        "gold_fix": "reverse of mutation.patch",
        "allowed_shared": d.allowed_shared,
        "allowed_terms": d.allowed_terms,
    }
    _write(datasets / "cases" / cid / "meta.json", json.dumps(meta, indent=2) + "\n")
    for name, text in d.reproducer_files.items():
        _write(datasets / "reproducers" / cid / name, text)
    for name, text in d.hidden_files.items():
        _write(datasets / "hidden_tests" / cid / name, text)


def write_manifest(builts: list[BuiltCase], path: Path) -> None:
    rows = [
        b.manifest.model_dump(mode="json") for b in sorted(builts, key=lambda b: b.manifest.case_id)
    ]
    _write(path, json.dumps(rows, indent=2) + "\n")


def materialize(patch: str, out: Path, lab: Path | None = None) -> Path:
    """Fresh copy of the pristine lab at `out/lab` with the mutation applied; returns `out`."""
    lab = lab or lab_tree.repo_root() / "lab"
    if out.exists():
        shutil.rmtree(out)
    lab_tree.copy_lab(lab, out)
    if patch:
        apply_patch(out, patch)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="traceforge.faultgen.generate")
    ap.add_argument("--datasets", type=Path, default=lab_tree.datasets_dir())
    ap.add_argument("--tree-out", type=Path, help="also write the faulty tree of --case here")
    ap.add_argument("--case")
    args = ap.parse_args(argv)
    lab = lab_tree.repo_root() / "lab"
    builts = [build_case(d, lab, split="dev") for d in seed_drafts(lab)]
    for b in builts:
        write_case(b, args.datasets)
    write_manifest(builts, args.datasets / "manifests" / "dev.json")
    print(f"base_sha={builts[0].manifest.base_sha}")
    for b in builts:
        m = b.manifest
        print(
            f"{m.case_id}  {m.cause_class:<22} {m.fault_family:<20} distance={m.distance} log={m.log_format}"
        )
    if args.tree_out:
        pick = next(b for b in builts if b.manifest.case_id == args.case)
        materialize(pick.patch, args.tree_out, lab)
        print(f"faulty tree for {args.case} written to {args.tree_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
