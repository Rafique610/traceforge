"""Hash manifest that freezes completed runs: every file's sha256, verified before reuse.

`python -m traceforge.evaluation.freeze_manifest build --out M --dir D [--dir D ...] [--file F]`
`python -m traceforge.evaluation.freeze_manifest verify M`
A frozen run is never rewritten: later stages read from it (saved diagnoses and evidence) only
after `verify_files` confirms the bytes are the ones frozen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build(dirs: list[Path], files: list[Path], root: Path) -> dict:
    entries: dict[str, str] = {}
    for d in dirs:
        for p in sorted(Path(d).rglob("*")):
            if p.is_file():
                entries[p.relative_to(root).as_posix()] = _sha(p)
    for f in files:
        entries[Path(f).relative_to(root).as_posix()] = _sha(Path(f))
    return {"root": str(root), "n_files": len(entries), "files": entries}


def verify_files(manifest: dict, paths: list[Path], root: Path) -> list[str]:
    """Problems (empty = all frozen and unchanged) for the given files."""
    problems = []
    for p in paths:
        rel = Path(p).resolve().relative_to(root.resolve()).as_posix()
        want = manifest["files"].get(rel)
        if want is None:
            problems.append(f"not frozen: {rel}")
        elif not Path(p).is_file() or _sha(Path(p)) != want:
            problems.append(f"changed or missing: {rel}")
    return problems


def verify_all(manifest: dict, root: Path) -> list[str]:
    return verify_files(manifest, [root / rel for rel in manifest["files"]], root)


def manifest_sha256(manifest: dict) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--dir", type=Path, action="append", default=[])
    b.add_argument("--file", type=Path, action="append", default=[])
    b.add_argument("--root", type=Path, default=Path(".."))
    v = sub.add_parser("verify")
    v.add_argument("manifest", type=Path)
    v.add_argument("--root", type=Path, default=Path(".."))
    a = ap.parse_args(argv)
    root = a.root.resolve()
    if a.cmd == "build":
        if a.out.exists():
            raise SystemExit(f"refused: {a.out} exists (a frozen manifest is never overwritten)")
        m = build([d.resolve() for d in a.dir], [f.resolve() for f in a.file], root)
        a.out.write_text(json.dumps(m, indent=1), "utf-8")
        print(f"froze {m['n_files']} files, manifest sha256 {manifest_sha256(m)}")
        return 0
    m = json.loads(a.manifest.read_text("utf-8"))
    bad = verify_all(m, root)
    print("OK: all frozen files unchanged" if not bad else "\n".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
