"""Symptoms exist for every committed case, are deterministic and pass the repo's leakage scan."""

import json
from pathlib import Path

import pytest

from traceforge.agent.symptoms import symptom_for
from traceforge.contracts.case_manifest import CaseManifest
from traceforge.faultgen.leakage import gold_terms, scan_visible

DATASETS = Path(__file__).resolve().parents[3] / "datasets"


def _cases() -> list[CaseManifest]:
    rows = []
    for split in ("test", "dev"):
        rows += json.loads((DATASETS / "manifests" / f"{split}.json").read_text("utf-8"))
    return [CaseManifest.model_validate(r) for r in rows]


CASES = _cases()


def test_all_184_cases_have_a_clean_deterministic_symptom():
    assert len(CASES) == 184
    for c in CASES:
        text = symptom_for(c, DATASETS)
        assert text.strip(), c.case_id
        assert text == symptom_for(c, DATASETS)
        meta = json.loads((DATASETS / "cases" / c.case_id / "meta.json").read_text("utf-8"))
        srcs = {
            s.path: (DATASETS.parent / s.path).read_text("utf-8")
            for s in c.gold_symbols
            if (DATASETS.parent / s.path).is_file()
        }
        terms = gold_terms(c, srcs, meta.get("runtime", {}))
        assert scan_visible({c.case_id: text}, terms) == [], c.case_id


@pytest.mark.parametrize("cid", ["shop_api-005", "shop_api-007", "shop_api-009"])
def test_runtime_metadata_shapes_the_text(cid):
    c = next(x for x in CASES if x.case_id == cid)
    text = symptom_for(c, DATASETS)
    assert ("live incident" in text) == (cid == "shop_api-007")
    assert ("logs are not available" in text) == (cid == "shop_api-009")
