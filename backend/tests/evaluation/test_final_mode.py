# ruff: noqa: E501
"""Final-evaluation mode: only RC1, only the frozen selection, only with the matching fingerprint."""

import json
from types import SimpleNamespace as N

import pytest
from test_eval_runner import QUIET, SAMPLES, fake
from test_v5_patch_stage import loader, make_saved_run

from traceforge.evaluation import runner
from traceforge.evaluation.fingerprint import code_fingerprint
from traceforge.evaluation.real_run import MissingInputs


def args(tmp_path, **kw):
    sel = tmp_path / "selection.json"
    sel.write_text(json.dumps({"cases": ["shop_api-050", "shop_api-051"]}), "utf-8")
    base = dict(
        pipeline="v5", split="test", diagnose_only=False, out=tmp_path / "results" / "final",
        provider="axforge", model="glm-5.3-flash", selection=sel,
        rc_fingerprint=code_fingerprint()["sha256"], case_ids=["shop_api-050"],
    )  # fmt: skip
    return N(**{**base, **kw})


def test_a_correct_final_invocation_is_allowed(tmp_path):
    assert runner._final_refusal(args(tmp_path)) is None


@pytest.mark.parametrize(
    "change,why",
    [
        ({"split": "dev"}, "--pipeline v5 --split test"),
        ({"pipeline": "v4"}, "--pipeline v5 --split test"),
        ({"diagnose_only": True}, "--pipeline v5 --split test"),
        ({"out": "SAME/development"}, "under 'final'"),
        ({"provider": "beatapi", "model": "glm-5.3-flash-free"}, "AxForge glm-5.3-flash only"),
        ({"selection": None}, "--selection"),
        ({"rc_fingerprint": None}, "--selection"),
        ({"case_ids": ["shop_api-999"]}, "frozen selection"),
        ({"case_ids": None}, "frozen selection"),
        ({"rc_fingerprint": "0" * 64}, "fingerprint differs"),
    ],
)
def test_every_unsafe_final_invocation_is_refused(tmp_path, change, why):
    if change.get("out") == "SAME/development":
        change = {**change, "out": tmp_path / "results" / "development"}
    assert why in runner._final_refusal(args(tmp_path, **change))


def test_final_mode_cannot_be_used_through_the_dev_path_and_main_refuses(tmp_path):
    argv = ["--manifest", "m.json", "--condition", "L0", "--run-id", "final-x", "--split", "test",
            "--out", str(tmp_path / "development"), "--pipeline", "v5", "--final-rc1"]  # fmt: skip
    assert runner.main(argv) == 2


def test_a_staged_run_starts_at_its_replicate_index(tmp_path):
    cases = []
    for i in range(2):
        c = json.loads((SAMPLES / "case_manifest.code.json").read_text("utf-8"))
        c.update(case_id=f"case-{i}", split="dev")
        cases.append(c)
    man = tmp_path / "data" / "manifest.json"
    man.parent.mkdir()
    man.write_text(json.dumps(cases), "utf-8")
    seen = []

    def run_fn(case, cond, rep):
        seen.append((case.case_id, rep))
        return fake()(case, cond, rep)

    out = runner.run_experiment(
        man, "L0", "dev-r", run_fn, tmp_path / "d", 1, "dev", **QUIET, replicate_start=1
    )
    runner.run_experiment(
        man, "L0", "dev-r", run_fn, tmp_path / "d", 2, "dev", **QUIET, replicate_start=1
    )
    assert [r for _c, r in seen] == [1, 1, 2, 2]  # r1 then r1 skipped on resume... (see below)
    assert sorted(p.name for p in (out / "records").iterdir()) == [
        "case-0.r1.json", "case-0.r2.json", "case-1.r1.json", "case-1.r2.json",
    ]  # fmt: skip


def test_shared_diagnosis_only_within_the_same_arm(tmp_path):
    root, run = make_saved_run(tmp_path, condition="L0")
    case = N(case_id="shop_api-096")
    with pytest.raises(MissingInputs, match="L0/v5"):
        loader(root, run)(case, "L1", 0)  # not shared: refused
    from traceforge.evaluation.real_run import make_real_run_fn

    def shared(cond):
        fn = make_real_run_fn(root / "datasets" / "manifests" / "dev.json", root / "runs" / "evidence",
                              root / "results" / "development" / "x", "axforge", "glm-5.3-flash",
                              pipeline="v5", patch_from=run, share_diagnosis=True)  # fmt: skip
        return fn.load_saved(case, cond, 0)

    sub, _ev, source = shared("L1")
    assert source["shared_diagnosis"] is True and source["diagnosis_condition"] == "L0"
    with pytest.raises(MissingInputs):
        shared("G1")  # a G-arm run can never take the L arm's diagnosis


def test_shared_abstention_is_reproduced_without_any_model_call(tmp_path):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[1] / "agent"))
    from agentfakes import FakeChat
    from test_v5_diagnose import FakeCtx, _Cases, _Evidence

    from traceforge.agent.pipeline import Sources, run_case
    from traceforge.agent.tools import SubmitDiagnosisV2
    from traceforge.evaluation.real_run import make_real_run_fn

    for text, reason, expect in (
        ('{"cause_class": "insufficient_evidence"}', None, "insufficient_evidence"),
        ("null", "budget_exhausted", "budget_exhausted"),
    ):
        root, run = make_saved_run(tmp_path / expect, condition="L0")
        (run / "cases" / "shop_api-096.r0" / "diagnosis.json").write_text(text, "utf-8")
        (run / "records" / "shop_api-096.r0.json").write_text(
            json.dumps({"condition": "L0", "pipeline_version": "v5", "failure_reason": reason}),
            "utf-8",
        )
        fn = make_real_run_fn(root / "datasets" / "manifests" / "dev.json", root / "runs" / "evidence",
                              root / "results" / "development" / "x", "axforge", "glm-5.3-flash",
                              pipeline="v5", patch_from=run, share_diagnosis=True)  # fmt: skip
        sub, ev, source = fn.load_saved(N(case_id="shop_api-096"), "L1", 0)
        assert isinstance(sub, SubmitDiagnosisV2) and sub.cause_class == "insufficient_evidence"
        chat = FakeChat()
        rec = run_case(_Cases().get("x"), "L1", Sources(_Cases(), _Evidence(), FakeCtx()),
                       chat_fn=chat, pipeline="v5", saved=(sub, ev, source["source_failure_reason"]))  # fmt: skip
        assert chat.n == 0 and rec.diagnosis.abstained and rec.outcome == "NO_PATCH"
        assert rec.failure_reason == expect and rec.tokens_in == 0
