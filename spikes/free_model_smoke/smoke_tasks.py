"""Task loading plus adapters onto the REAL pipeline interfaces (ToolContext, ContextBundle).

A task is `tasks/<id>.json` (evidence, ground truth) + `tasks/<id>/lab/shop_api/*` (code) +
`tasks/<id>/tests/visible_check.py` + `tasks/<id>/hidden_check.py` (scorer-only, never rendered).
Spike code: never imported by backend/.
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from traceforge.agent.tools import ToolContext
from traceforge.contracts.case_manifest import CaseManifest, GoldSymbol
from traceforge.contracts.context import ContextBundle, ContextHit
from traceforge.contracts.evidence import EvidenceBundle, EvidenceItem

HERE = Path(__file__).resolve().parent
TASKS_DIR = HERE / "tasks"
REPAIRABLE = ("configuration", "application_code")


@dataclass
class Task:
    data: dict[str, Any]
    root: Path  # tasks/<id>/

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def cause_class(self) -> str:
        return self.data["cause_class"]

    @property
    def target(self) -> str | None:
        return self.data["target"]

    @property
    def repairable(self) -> bool:
        return self.cause_class in REPAIRABLE

    def lab_files(self) -> dict[str, str]:
        """Every text file under lab/ keyed by repo-style POSIX path (lab/shop_api/x.py)."""
        return {
            p.relative_to(self.root).as_posix(): p.read_text("utf-8")
            for p in sorted((self.root / "lab").rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts
        }

    def visible_sources(self) -> list[str]:
        vc = self.data.get("visible_check")
        return [(TASKS_DIR / vc).read_text("utf-8")] if vc else []


def load_tasks(
    only: list[str] | None = None, tasks_dir: Path = TASKS_DIR
) -> list[Task]:
    out = []
    for f in sorted(tasks_dir.glob("*.json")):
        data = json.loads(f.read_text("utf-8"))
        if only and data["id"] not in only:
            continue
        out.append(Task(data, tasks_dir / data["id"]))
    if only and {t.id for t in out} != set(only):
        raise SystemExit(
            f"unknown task id(s): {sorted(set(only) - {t.id for t in out})}"
        )
    return out


def _find(tree: ast.AST, qualname: str) -> ast.AST | None:
    node: ast.AST = tree
    for part in qualname.split("."):
        node = next(
            (
                n
                for n in getattr(node, "body", [])
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and n.name == part
            ),
            None,
        )
        if node is None:
            return None
    return node


class SmokeContext:
    """ContextSource over the task's own files (read_symbol via ast; no code graph)."""

    def __init__(self, task: Task) -> None:
        self.files = task.lab_files()

    def span(self, path: str, qualname: str) -> tuple[int, int, str] | None:
        text = self.files.get(path)
        if text is None or not path.endswith(".py"):
            return None
        node = _find(ast.parse(text), qualname)
        if node is None:
            return None
        lines = text.splitlines()[node.lineno - 1 : node.end_lineno]
        return node.lineno, node.end_lineno, "\n".join(lines)

    def read_symbol(self, case: CaseManifest, path: str, qualname: str) -> str | None:
        s = self.span(path, qualname)
        return s[2] if s else None

    def neighbors(self, node_id: str) -> list[str]:
        return []

    def retrieve(self, *a: Any, **k: Any) -> ContextBundle:  # protocol completeness
        raise NotImplementedError


def build_tool_context(task: Task) -> tuple[ToolContext, ContextBundle]:
    d, ctx = task.data, SmokeContext(task)
    items = [
        EvidenceItem(
            id=e["id"],
            kind=e["kind"],
            service=d["service"],
            content=e["content"],
            sha256=hashlib.sha256(e["content"].encode()).hexdigest(),
            path=e.get("path"),
            line=e.get("line"),
        )
        for e in d["evidence"]
    ]
    evidence = EvidenceBundle(
        incident_id=task.id,
        base_sha="smoke",
        compose_sha256=hashlib.sha256(b"smoke").hexdigest(),
        items=items,
    )
    keys, syms = [], []
    if task.cause_class == "configuration":
        keys = [task.target]
    elif task.cause_class == "application_code":
        path, qual = task.target.split("::")
        a, b, _ = ctx.span(path, qual)
        syms = [GoldSymbol(path=path, qualname=qual, start_line=a, end_line=b)]
    case = CaseManifest(
        case_id=task.id,
        split="dev",
        cause_class=task.cause_class,
        fault_family=d["category"],
        service=d["service"],
        base_sha="smoke",
        gold_config_keys=keys,
        gold_symbols=syms,
        distance=1 if task.repairable else None,
        reproducer_id="smoke",
        hidden_test_ids=["hidden_check"] if task.repairable else [],
        variant_group=task.id,
    )
    hits = []
    for i, c in enumerate(d["context"]):
        a, b, src = ctx.span(c["path"], c["qualname"])
        hits.append(
            ContextHit(
                node_id=f"{c['path']}::{c['qualname']}",
                kind="symbol",
                path=c["path"],
                start_line=a,
                end_line=b,
                score=1.0 - 0.1 * i,
                reasons=["smoke"],
                excerpt=src,
            )
        )
    bundle = ContextBundle(
        incident_id=task.id, mode="L", token_budget=10_000, tokens_used=0, hits=hits
    )
    return ToolContext(case=case, evidence=evidence, ctx=ctx), bundle
