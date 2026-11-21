# ruff: noqa: E501
"""The pristine lab tree: how `base_sha` is defined, copying it, and applying patches to a copy.

base_sha = SHA-1 over the sorted lines `<repo-relative POSIX path>\0<sha256 of LF-normalised bytes>\n`
for every file under `lab/` except caches, `.env` and compiled files. The repo is not a git repository
here, so this content hash plays the role of the commit id: it changes iff a lab file changes.
"""

import hashlib
import shutil
from pathlib import Path

_SKIP_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "node_modules"}
_SKIP_FILES = {".env"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def datasets_dir() -> Path:
    return repo_root() / "datasets"


def lab_files(lab: Path) -> list[Path]:
    out = []
    for p in sorted(lab.rglob("*")):
        rel = p.relative_to(lab)
        if p.is_dir() or _SKIP_DIRS & set(rel.parts):
            continue
        if p.name in _SKIP_FILES or p.suffix == ".pyc":
            continue
        out.append(p)
    return out


def base_sha(lab: Path) -> str:
    h = hashlib.sha1()
    for p in lab_files(lab):
        rel = "lab/" + p.relative_to(lab).as_posix()
        digest = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        h.update(f"{rel}\0{digest}\n".encode())
    return h.hexdigest()


def copy_lab(lab: Path, dest_root: Path) -> Path:
    """Copy the pristine lab to `<dest_root>/lab` (the tree layout manifests use); returns dest_root."""
    for p in lab_files(lab):
        target = dest_root / "lab" / p.relative_to(lab)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
    return dest_root


def read_lf(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")
