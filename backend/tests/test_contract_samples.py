import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from traceforge.contracts import CONTRACTS, CaseManifest, ContextBundle, Diagnosis

SAMPLES = Path(__file__).parents[1] / "traceforge" / "contracts" / "samples"
FILES = sorted(SAMPLES.glob("*.json"))


def test_three_samples_per_contract():
    names = [f.name.split(".")[0] for f in FILES]
    assert {n: names.count(n) for n in CONTRACTS} == dict.fromkeys(CONTRACTS, 3)


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_sample_validates_and_round_trips(path: Path):
    model = CONTRACTS[path.name.split(".")[0]]
    obj = model.model_validate_json(path.read_text(encoding="utf-8"))
    assert model.model_validate_json(obj.model_dump_json()) == obj


def _load(name: str) -> dict:
    return json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def test_repairable_case_needs_target():
    data = _load("case_manifest.config") | {"gold_config_keys": [], "gold_symbols": []}
    with pytest.raises(ValidationError, match="gold config key or symbol"):
        CaseManifest.model_validate(data)


def test_context_within_budget():
    data = _load("context_bundle.config") | {"tokens_used": 5000}
    with pytest.raises(ValidationError, match="token_budget"):
        ContextBundle.model_validate(data)


def test_windows_paths_rejected():
    data = _load("case_manifest.code")
    data["gold_symbols"][0]["path"] = r"C:\lab\shop_api\app\orders.py"
    with pytest.raises(ValidationError):
        CaseManifest.model_validate(data)


def test_diagnosis_must_cite_evidence():
    with pytest.raises(ValidationError, match="evidence_ids"):
        Diagnosis(cause_class="configuration", target="worker.REDIS_HOST")
