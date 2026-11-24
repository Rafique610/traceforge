# ruff: noqa: E501
"""Provenance-based feedback, iterative repair attempts, frozen patch, scope/policy robustness."""

import hashlib

import pytest
from conftest import CORRECT, WRONG, real_runner
from test_loop import ALLOW, HIDDEN_ID, Fake, go, res

from traceforge.contracts.test_run import TestOutcome, TestRunResult
from traceforge.repair import policy, run_repair
from traceforge.repair.feedback import (
    FEEDBACK_CAP,
    FeedbackError,
    FeedbackItem,
    build_feedback,
    summarize_edit,
)
from traceforge.repair.scope import REASON, describe_reasons, make_scope_check

PYTEST_FAIL = """\
F                                                                        [100%]
=================================== FAILURES ===================================
______________________________ test_ten_percent ________________________________

    def test_ten_percent():
>       assert discount(200, 10) == 180
E       assert 0 == 180
E        +  where 0 = discount(200, 10)

tests/test_repro.py:5: AssertionError
=========================== short test summary info ============================
FAILED tests/test_repro.py::test_ten_percent - assert 0 == 180
1 failed in 0.02s
"""


VIS_FAIL = WRONG.replace("price - pct * 2", "price * 2")  # fails reproducer and visible suite


def run(tail, failed=1, ids=("tests/test_repro.py::test_ten_percent",)):
    return TestRunResult(
        passed=0,
        failed=failed,
        stdout_tail=tail,
        duration_ms=1,
        timed_out=False,
        tests=[TestOutcome(id=i, outcome="failed") for i in ids],
    )


# --- provenance ------------------------------------------------------------------------------


def test_feedback_item_from_visible_runs_has_provenance():
    it = FeedbackItem.from_run("reproducer", run(PYTEST_FAIL))
    assert it.source == "visible_reproducer" and it.suite == "reproducer"
    assert it.test_ids == ("tests/test_repro.py::test_ten_percent",)
    assert it.sha256 == hashlib.sha256(it.text.encode()).hexdigest()
    assert FeedbackItem.from_run("visible", run("x")).source == "visible_suite"


@pytest.mark.parametrize("suite", ["hidden", "other", ""])
def test_hidden_result_is_structurally_rejected(suite):
    with pytest.raises(FeedbackError):
        FeedbackItem.from_run(suite, run(f"{HIDDEN_ID} failed"))


def test_item_cannot_be_forged_with_hidden_suite_or_wrong_hash():
    with pytest.raises(FeedbackError):
        FeedbackItem("visible_suite", "hidden", (), "t", hashlib.sha256(b"t").hexdigest())  # type: ignore[arg-type]
    with pytest.raises(FeedbackError):
        FeedbackItem("visible_suite", "visible", (), "t", "0" * 64)


def test_feedback_shows_assertion_expected_vs_actual_not_only_the_tail():
    noise = "x" * 3500  # a long noisy log before the failure section
    item = FeedbackItem.from_run("reproducer", run(noise[:300] + PYTEST_FAIL))
    assert "assert 0 == 180" in item.text and "discount(200, 10)" in item.text
    assert "test_ten_percent" in item.text and "====" not in item.text
    assert noise[:100] not in item.text


def test_feedback_is_capped_and_falls_back_to_the_tail():
    items = build_feedback(run("y" * 4000, ids=()), run("z" * 4000, ids=()))
    assert sum(len(i.text) for i in items) + 1 <= FEEDBACK_CAP
    assert items[0].text.startswith("reproducer:") and items[1].text.startswith("visible suite:")


def test_short_reproducer_leaves_budget_to_the_visible_suite():
    items = build_feedback(run("ok"), run("v" * 4000, ids=()))
    assert len(items[1].text) > FEEDBACK_CAP // 2


# --- loop: recorded provenance, F0/F1, iterative prompts --------------------------------------


def test_attempt_records_exact_feedback_with_provenance(repo):
    r, prompts = go(repo, Fake(), "F1")
    a1, a2, a3 = r.attempts
    assert a1.feedback is None and a1.feedback_items == () and a1.feedback_sha256 is None
    for att, (_, fb) in zip((a2, a3), prompts[1:], strict=True):
        assert att.feedback == fb  # the exact text delivered
        assert att.feedback_sha256 == hashlib.sha256(fb.encode()).hexdigest()
        assert {i.suite for i in att.feedback_items} == {"reproducer", "visible"}
        assert all(i.source.startswith("visible") for i in att.feedback_items)
        assert len(fb) <= FEEDBACK_CAP
    assert "t::vis" in a2.feedback_items[1].test_ids


def test_f0_records_no_feedback_at_all(repo):
    r, prompts = go(repo, Fake(), "F0")
    assert all(a.feedback is None and a.feedback_items == () for a in r.attempts)
    assert [fb for _, fb in prompts] == [None] * 3


def test_second_attempt_sees_previous_edit_and_visible_output_not_hidden(repo):
    hidden = res(failed=1, tail=f"{HIDDEN_ID} assertion line", ids=[HIDDEN_ID])
    r, prompts = go(repo, Fake(hidden=hidden), "F1", proposals=[VIS_FAIL, CORRECT, CORRECT])
    fb = prompts[1][1]
    assert "VISIBLE FAIL line" in fb  # previous attempt's actual visible output
    assert "your previous edit" in fb and "price * 2" in fb  # what it tried (visible side)
    assert HIDDEN_ID not in fb and "assertion line" not in fb
    assert r.attempts[0].edit_summary and "price * 2" in r.attempts[0].edit_summary


def test_rejected_attempt_does_not_replace_visible_feedback_with_edit_errors(repo):
    bad = "<<<<<<< SEARCH shop.py\nnot there\n=======\nx\n>>>>>>> REPLACE"
    r, prompts = go(repo, Fake(), "F1", proposals=[VIS_FAIL, bad, VIS_FAIL])
    assert "VISIBLE FAIL line" in prompts[2][1]  # attempt 3 still sees attempt 1's test output
    assert "no_match" not in prompts[2][1] and "not found" not in prompts[2][1]
    assert r.attempts[1].reasons == ["no_match"] and "SEARCH text was not found" in (
        r.attempts[1].rejection_text or ""
    )


def test_hidden_runs_once_and_attempts_are_recorded_with_real_runner(repo):
    seen = []

    def runner(req):
        seen.append(req.suite)
        return real_runner(req)

    r, prompts = go(repo, runner, "F1", proposals=[VIS_FAIL, CORRECT])
    assert r.outcome == "TEST_VERIFIED_IN_LAB" and len(r.attempts) == 2 and len(prompts) == 2
    assert seen.count("hidden") == 1 and seen[-1] == "hidden"
    assert prompts[1][1] and "assert" in prompts[1][1]  # the real pytest assertion text reached it
    assert r.attempts[0].visible_passed is False and r.attempts[1].visible_passed is True


def test_legacy_style_keeps_the_v4_feedback_text(repo):
    path, sha = repo
    got = []

    def propose(_c, fb):
        got.append(fb)
        return WRONG

    r = run_repair(
        case_id="c", repo_path=path, base_sha=sha, condition="F1", context=None,
        propose_edit=propose, run_tests=Fake(), allowlist=ALLOW, feedback_style="legacy",
    )  # fmt: skip
    assert got[1].startswith("reproducer:\nrepro FAIL\nvisible suite:\nVISIBLE FAIL line\nfailing:")
    assert "your previous edit" not in got[1] and len(r.attempts) == 3


# --- sandbox robustness -----------------------------------------------------------------------


def test_runner_exception_is_a_sandbox_error_not_a_crash(repo):
    def boom(req):
        raise OSError("docker down")

    r, p = go(repo, boom)
    assert (r.outcome, r.reason) == ("UNVERIFIED", "sandbox_error") and p == []
    assert "docker down" in (r.detail or "")


def test_timeout_detail_is_recorded(repo):
    r, _ = go(repo, Fake(visible=res(timed_out=True, error="timeout")))
    assert r.reason == "sandbox_error" and "timeout" in (r.detail or "")
    assert r.attempts[0].sandbox_detail


def test_baseline_worktree_failure_is_unverified(repo, monkeypatch):
    from traceforge.repair import loop
    from traceforge.repair.worktree import WorktreeError

    def broken(*a, **k):
        raise WorktreeError("git worktree failed")

    monkeypatch.setattr(loop, "worktree", broken)
    r, _ = go(repo, Fake())
    assert (r.outcome, r.reason) == ("UNVERIFIED", "sandbox_error") and "worktree" in r.detail


# --- frozen patch / hash ----------------------------------------------------------------------


def test_result_diff_and_hash_are_consistent_and_immutable_after_hidden_run(repo):
    r, _ = go(repo, real_runner, proposals=[CORRECT])
    assert r.outcome == "TEST_VERIFIED_IN_LAB" and r.hidden_result is not None
    assert r.patch_consistent()
    assert r.patch_sha256 == hashlib.sha256(r.diff.encode("utf-8")).hexdigest()
    assert r.transition_payload()["patch_sha256"] == r.patch_sha256
    assert r.diff == r.attempts[0].diff  # the stored diff is the verified attempt's diff
    for name, val in (("diff", "tampered"), ("patch_sha256", "0" * 64)):
        with pytest.raises(AttributeError):
            setattr(r, name, val)
    assert r.patch_consistent()


# --- scope / policy ---------------------------------------------------------------------------

CODE = "import os\n\n\ndef total(items):\n    return sum(items[1:])\n\n\ndef other(x):\n    return x + 1\n"


def code_diag():
    from traceforge.agent.tools import SubmitDiagnosis

    return SubmitDiagnosis(
        cause_class="application_code", path="a.py", qualname="total", supporting_evidence_ids=["E"]
    )


def test_import_added_at_module_top_is_allowed_with_the_fix():
    check = make_scope_check(code_diag())
    new = CODE.replace("import os\n", "import os\nimport math\n").replace(
        "sum(items[1:])", "math.fsum(items)"
    )
    assert check({"a.py": CODE}, {"a.py": new}) == []


def test_non_import_insertion_or_import_inside_other_function_still_rejected():
    check = make_scope_check(code_diag())
    assert check({"a.py": CODE}, {"a.py": CODE.replace("import os\n", "import os\nX = 1\n")})
    assert check(
        {"a.py": CODE},
        {"a.py": CODE.replace("    return x + 1", "    import math\n    return x + 1")},
    )
    # an import placed after the first function is not a top-of-module import
    assert check({"a.py": CODE}, {"a.py": CODE + "import math\n"})
    # modifying an existing import line is not an insertion
    assert check({"a.py": CODE}, {"a.py": CODE.replace("import os", "import sys")})


def test_describe_reasons_is_readable():
    t = describe_reasons([f"{REASON}:a.py:9", "no_match", "test_literal:shop.py"])
    assert (
        "outside the diagnosed" in t and "SEARCH text was not found" in t and "visible tests" in t
    )


def test_config_syntax_check_blames_only_the_edit():
    ok, bad = '{"a": 1}', '{"a": '
    r = policy.check_patch("+x\n", {"c.json": ok}, {"c.json": bad})
    assert r.reasons == ["syntax_error:c.json"]
    assert policy.check_patch("+x\n", {"c.json": ok}, {"c.json": '{"a": 2}'}).ok
    assert policy.check_patch("+x\n", {"c.json": bad}, {"c.json": bad}).ok  # already broken
    assert policy.check_patch("+x\n", {"c.toml": "a = 1\n"}, {"c.toml": "a = = 1\n"}).reasons == [
        "syntax_error:c.toml"
    ]
    assert policy.check_patch("+x\n", {"c.ini": "a=1\n"}, {"c.ini": "a=2\n"}).ok


def test_summarize_edit_is_bounded_and_lists_changed_lines_only():
    diff = "diff --git a/s.py b/s.py\n--- a/s.py\n+++ b/s.py\n@@ -1 +1 @@\n-old line\n+new line\n"
    assert summarize_edit(diff) == "in s.py:\n-old line\n+new line"
    assert len(summarize_edit("+" + "x" * 5000)) <= 450
