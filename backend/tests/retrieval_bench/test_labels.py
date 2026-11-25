# ruff: noqa: E501
"""Structural checks of the committed benchmark labels (not a retrieval result). Needs the pinned
clones under runs/bench_repos/ (skipped if absent)."""

import pytest

from traceforge.retrieval_bench.repo_ctx import build_context
from traceforge.retrieval_bench.suite import (
    BENCH_DIR,
    REPO_ROOT,
    load_pins,
    load_query_file,
    validate_queries,
    verify_pin,
)
from traceforge.retrieval_bench.types import QUERY_TYPES

PINS = load_pins(BENCH_DIR)


def test_three_tiers_pinned():
    assert [p["tier"] for p in PINS] == ["small", "medium", "complex"]
    for p in PINS:
        assert len(p["commit"]) == 40 and p["license"] and p["size_bytes"] > 0


@pytest.mark.parametrize("pin", PINS, ids=lambda p: p["name"])
def test_labels_valid_against_pinned_tree(pin):
    root = REPO_ROOT / pin["path"]
    if not root.is_dir():
        pytest.skip(f"{root} not cloned")
    verify_pin(pin, root)
    q = load_query_file(BENCH_DIR / pin["queries"])
    assert validate_queries(q, build_context(pin["name"], root)) == []
    assert {x["type"] for x in q["queries"]} == set(QUERY_TYPES)
    assert len(q["queries"]) >= 12
