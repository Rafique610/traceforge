from pathlib import Path

import pytest

from traceforge.evaluation import errors, real_run, runner


def test_tier_only_axforge_glm_is_official():
    assert real_run.tier_for("axforge", "glm-5.3-flash") == "official"
    assert real_run.tier_for("beatapi", "glm-5.3-flash-free") == "development"
    assert real_run.tier_for("axforge", "other-model") == "development"
    assert real_run.tier_for("ollama", "qwen2.5-coder:7b") == "development"


def test_missing_evidence_means_not_ready_and_no_model_call(tmp_path):
    from traceforge.contracts.case_manifest import CaseManifest

    sample = Path(__file__).resolve().parents[2] / "traceforge/contracts/samples"
    case = CaseManifest.model_validate_json((sample / "case_manifest.code.json").read_text("utf-8"))
    run_fn = real_run.make_real_run_fn(
        tmp_path / "datasets" / "manifests" / "m.json", tmp_path / "ev", tmp_path / "run",
        "beatapi", "glm-5.3-flash-free",
    )  # fmt: skip
    with pytest.raises(real_run.MissingInputs):
        run_fn.ready(case)
    with pytest.raises(real_run.MissingInputs):
        run_fn(case, "L0", 0)


def test_stop_run_is_one_class_for_runner_and_real_run():
    assert runner.StopRun is errors.StopRun is real_run.StopRun


def test_relative_paths_are_made_absolute_for_the_sandbox(tmp_path, monkeypatch):
    (tmp_path / "datasets" / "manifests").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    run_fn = real_run.make_real_run_fn(
        Path("datasets/manifests/dev.json"),
        Path("ev"),
        Path("run"),
        "beatapi",
        "glm-5.3-flash-free",
    )
    assert run_fn.datasets.is_absolute() and run_fn.datasets == (tmp_path / "datasets").resolve()
