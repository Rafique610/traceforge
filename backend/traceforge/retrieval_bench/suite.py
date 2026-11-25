# ruff: noqa: E501
"""Load the benchmark suite (benchmarks/retrieval/): repo pins, queries, gold. Gold is parsed into
`BenchQuery.gold` (scorer side); the `QueryText` handed to retrievers carries none of it."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from traceforge.retrieval_bench.repo_ctx import FORBIDDEN_PARTS, RepoContext, build_context
from traceforge.retrieval_bench.types import QUERY_TYPES, BenchQuery

REPO_ROOT = Path(__file__).resolve().parents[3]
BENCH_DIR = REPO_ROOT / "benchmarks" / "retrieval"


@dataclass
class Workload:
    suite: str  # repo name, or "dev"
    ctx: RepoContext
    queries: list[BenchQuery]
    tier: str = ""


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree_sha256(root: Path) -> str:
    """Content hash of a tree (relative POSIX paths + bytes, sorted; `.git` excluded)."""
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and ".git/" not in rel + "/" and not rel.startswith(".git/"):
            h.update(rel.encode() + b"\0" + hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def load_pins(bench_dir: Path = BENCH_DIR) -> list[dict]:
    return json.loads((bench_dir / "repos.json").read_text("utf-8"))["repos"]


def load_query_file(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))


def verify_pin(pin: dict, root: Path) -> None:
    """Fail if the checkout is not the pinned snapshot."""
    if (root / ".git").exists():
        head = subprocess.run(  # noqa: S603
            ["git", "-C", str(root), "rev-parse", "HEAD"],  # noqa: S607
            capture_output=True, text=True, check=True,
        ).stdout.strip()  # fmt: skip
        if head != pin["commit"]:
            raise RuntimeError(f"{pin['name']}: HEAD {head} != pinned {pin['commit']}")
    elif tree_sha256(root) != pin["content_sha256"]:
        raise RuntimeError(f"{pin['name']}: tree content hash differs from the pin")


def validate_queries(qfile: dict, ctx: RepoContext, min_queries: int = 12) -> list[str]:
    """Structural checks (not retrieval): types, >= min_queries, all six types, gold ids exist."""
    errs: list[str] = []
    qs = qfile["queries"]
    if len(qs) < min_queries:
        errs.append(f"{qfile['repo']}: {len(qs)} < {min_queries} queries")
    missing = set(QUERY_TYPES) - {q["type"] for q in qs}
    if missing:
        errs.append(f"{qfile['repo']}: missing types {sorted(missing)}")
    seen: set[str] = set()
    for q in qs:
        if q["id"] in seen:
            errs.append(f"duplicate id {q['id']}")
        seen.add(q["id"])
        if q["type"] not in QUERY_TYPES:
            errs.append(f"{q['id']}: unknown type {q['type']}")
        if not q["gold"]:
            errs.append(f"{q['id']}: empty gold")
        for g in q["gold"]:
            if g["id"] not in ctx.corpus.by_hit:
                errs.append(f"{q['id']}: gold id not in corpus: {g['id']}")
            if not g.get("why"):
                errs.append(f"{q['id']}: gold {g['id']} has no justification")
    return errs


def load_workload(pin: dict, bench_dir: Path = BENCH_DIR, check: bool = True) -> Workload:
    root = (REPO_ROOT / pin["path"]).resolve()
    if check:
        verify_pin(pin, root)
    ctx = build_context(pin["name"], root)
    qfile = load_query_file(bench_dir / pin["queries"])
    if check and (errs := validate_queries(qfile, ctx)):
        raise ValueError("invalid labels:\n" + "\n".join(errs))
    queries = [
        BenchQuery(
            q["id"], q["type"], ctx.make_query(q["id"], q["text"], pin.get("service", "")),
            frozenset(g["id"] for g in q["gold"]),
        )
        for q in qfile["queries"]
    ]  # fmt: skip
    return Workload(pin["name"], ctx, queries, pin.get("tier", ""))


def assert_no_forbidden_paths(ctx: RepoContext) -> None:
    """Leakage guard: no indexed chunk lives under hidden tests / .git / mutation patches."""
    bad = [c.path for c in ctx.corpus.chunks if any(p in c.path.split("/") or c.path.endswith(p)
                                                      for p in FORBIDDEN_PARTS)]  # fmt: skip
    if bad:
        raise AssertionError(f"forbidden paths indexed: {sorted(set(bad))[:5]}")
