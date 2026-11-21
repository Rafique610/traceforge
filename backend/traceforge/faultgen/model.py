# ruff: noqa: E501
"""CaseDraft: what a template produces. `build_case` turns it into files + a CaseManifest."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from traceforge.contracts.case_manifest import CaseManifest, GoldSymbol
from traceforge.faultgen import lab_tree
from traceforge.faultgen.astspan import find_span, test_ids
from traceforge.faultgen.patching import make_patch

DistanceSource = Literal["manual", "graph"]


@dataclass
class CaseDraft:
    case_id: str
    cause_class: str
    fault_family: str
    service: str
    variant_group: str
    log_format: str
    distance: int | None
    template: str
    params: dict
    # repo-relative path -> new full text (LF). Empty for runtime/insufficient cases.
    edits: dict[str, str] = field(default_factory=dict)
    gold_config_keys: list[str] = field(default_factory=list)
    gold_symbols: list[tuple[str, str]] = field(default_factory=list)  # (path, qualname)
    reproducer_files: dict[str, str] = field(default_factory=dict)
    hidden_files: dict[str, str] = field(default_factory=dict)
    runtime: dict = field(default_factory=dict)  # runtime.yaml content (runtime/insufficient)
    notes: str = ""
    distance_source: DistanceSource = "manual"
    # input literals a hidden test may share with the visible one (contract boundary values), with the reason
    allowed_shared: dict[str, str] = field(default_factory=dict)
    # gold terms that are also public API names visible tests must use (e.g. a response field), with reason
    allowed_terms: dict[str, str] = field(default_factory=dict)


@dataclass
class BuiltCase:
    manifest: CaseManifest
    patch: str
    draft: CaseDraft


def visible_ids(lab: Path, service: str) -> list[str]:
    """Visible suite = the service's own tests minus tests/integration."""
    out: list[str] = []
    for f in sorted((lab / service / "tests").glob("test_*.py")):
        if f.name == "test_integration.py":
            continue
        out += test_ids(lab_tree.read_lf(f), f"lab/{service}/tests/{f.name}")
    return out


def build_case(draft: CaseDraft, lab: Path, split: str = "dev") -> BuiltCase:
    edits = {}
    for path, new in draft.edits.items():
        old = lab_tree.read_lf(lab.parent / path)
        edits[path] = (old, new)
    symbols = []
    for path, qual in draft.gold_symbols:
        start, end = find_span(draft.edits[path], qual)
        symbols.append(GoldSymbol(path=path, qualname=qual, start_line=start, end_line=end))
    rid = f"datasets/reproducers/{draft.case_id}"
    hid = f"datasets/hidden_tests/{draft.case_id}"
    repro = [
        t
        for n, s in sorted(draft.reproducer_files.items())
        if n.startswith("test_")
        for t in test_ids(s, f"{rid}/{n}")
    ]
    hidden = [
        t
        for n, s in sorted(draft.hidden_files.items())
        if n.startswith("test_")
        for t in test_ids(s, f"{hid}/{n}")
    ]
    manifest = CaseManifest(
        case_id=draft.case_id,
        split=split,  # type: ignore[arg-type]
        cause_class=draft.cause_class,  # type: ignore[arg-type]
        fault_family=draft.fault_family,
        service=draft.service,  # type: ignore[arg-type]
        base_sha=lab_tree.base_sha(lab),
        gold_config_keys=draft.gold_config_keys,
        gold_symbols=symbols,
        distance=draft.distance,
        reproducer_id=repro[0],
        visible_test_ids=visible_ids(lab, draft.service),
        hidden_test_ids=hidden,
        variant_group=draft.variant_group,
        log_format=draft.log_format,  # type: ignore[arg-type]
    )
    return BuiltCase(manifest, make_patch(edits), draft)
