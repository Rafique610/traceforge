from pathlib import Path

import pytest
from conftest import CORRECT, WRONG, real_runner

from traceforge.contracts.test_run import TestOutcome, TestRunResult
from traceforge.repair import run_repair
from traceforge.repair.worktree import worktree

HIDDEN_ID = "HIDDEN_SECRET_test_half_zz"
ALLOW = ["shop.py"]


def res(passed=0, failed=0, tail="", timed_out=False, error=None, ids=()):
    return TestRunResult(
        passed=passed,
        failed=failed,
        stdout_tail=tail,
        duration_ms=1,
        timed_out=timed_out,
        error=error,
        tests=[TestOutcome(id=i, outcome="failed") for i in ids],
    )


class Fake:
    """Scripted runner: reproducer fails on base; patched results come from `visible_ok`."""

    def __init__(self, visible_ok=False, hidden=None, visible=None):
        self.calls, self.visible_ok, self.visible = [], visible_ok, visible
        self.hidden = hidden or res(1, tail=f"{HIDDEN_ID} passed")

    def __call__(self, req):
        self.calls.append(req.suite)
        if req.suite == "hidden":
            return self.hidden
        if req.suite == "reproducer":
            base = self.calls.count("reproducer") == 1
            return res(failed=1, tail="repro FAIL") if base or not self.visible_ok else res(1)
        if self.visible:
            return self.visible
        return res(2) if self.visible_ok else res(1, 1, tail="VISIBLE FAIL line", ids=["t::vis"])


def go(repo, runner, cond="F1", proposals=None, **kw):
    path, sha = repo
    prompts = []
    it = iter(proposals or [CORRECT] * 3)

    def propose(ctx, fb):
        prompts.append((ctx, fb))
        return next(it)

    r = run_repair(
        case_id="c",
        repo_path=path,
        base_sha=sha,
        condition=cond,
        context="CTX",
        propose_edit=propose,
        run_tests=runner,
        allowlist=ALLOW,
        **kw,
    )
    return r, prompts


def test_real_correct_patch_verified(repo):
    r, p = go(repo, real_runner, proposals=[CORRECT])
    assert r.outcome == "TEST_VERIFIED_IN_LAB" and r.hidden_passed and len(p) == 1
    assert r.transition_payload()["repro_before"] == "failed"
    assert r.transition_payload()["repro_after"] == "passed"
    import hashlib

    assert r.patch_sha256 == hashlib.sha256(r.diff.encode()).hexdigest()


def test_real_wrong_patch_rejected_by_hidden(repo):
    r, _ = go(repo, real_runner, proposals=[WRONG])
    assert r.outcome == "REJECTED" and r.reason == "hidden_failed" and r.hidden_passed is False


def test_worktrees_cleaned_up(repo, tmp_path):
    root = tmp_path / "wtroot"
    root.mkdir()
    go(repo, real_runner, proposals=[CORRECT], worktree_root=str(root))
    assert list(root.iterdir()) == []
    with worktree(repo[0], repo[1], root=root) as wt:
        assert (Path(wt) / "shop.py").exists()


def test_equal_attempts_f0_f1(repo):
    r0, p0 = go(repo, Fake(), "F0")
    r1, p1 = go(repo, Fake(), "F1")
    assert len(p0) == len(p1) == 3 and len(r0.attempts) == len(r1.attempts) == 3
    assert [fb for _, fb in p0] == [None, None, None]
    assert p1[0][1] is None and all("VISIBLE FAIL line" in fb for _, fb in p1[1:])
    assert r0.outcome == r1.outcome == "REJECTED" and r0.reason == "visible_failed"


def test_no_hidden_leak_and_hidden_once(repo):
    hidden = res(failed=1, tail=f"{HIDDEN_ID} assertion line", ids=[HIDDEN_ID])
    fake = Fake(hidden=hidden)
    r, prompts = go(repo, fake, "F1")
    assert fake.calls.count("hidden") == 1 and fake.calls[-1] == "hidden"
    blob = repr(prompts)
    assert HIDDEN_ID not in blob and "assertion line" not in blob
    assert HIDDEN_ID in r.hidden_result.stdout_tail
    assert HIDDEN_ID not in repr(r.attempts) and HIDDEN_ID not in repr(r.transition_payload())


def test_early_stop_on_visible_pass(repo):
    fake = Fake(visible_ok=True)
    r, p = go(repo, fake)
    assert len(p) == 1 and r.outcome == "TEST_VERIFIED_IN_LAB"
    assert fake.calls.count("hidden") == 1


@pytest.mark.parametrize("where", ["baseline", "visible", "hidden"])
def test_timeout_is_unverified(repo, where):
    to = res(timed_out=True, error="timeout")
    if where == "baseline":
        fake = lambda req: to  # noqa: E731
    elif where == "visible":
        fake = Fake(visible=to)
    else:
        fake = Fake(visible_ok=True, hidden=to)
    r, _ = go(repo, fake)
    assert r.outcome == "UNVERIFIED" and r.reason == "sandbox_error" and r.hidden_passed is None


def test_fault_not_reproduced(repo):
    r, p = go(repo, lambda req: res(1))
    assert r.outcome == "UNVERIFIED" and r.reason == "fault_not_reproduced" and p == []


def test_invalid_edits_use_attempts_and_no_patch(repo):
    bad = "<<<<<<< SEARCH shop.py\nnot there\n=======\nx\n>>>>>>> REPLACE"
    esc = "<<<<<<< SEARCH ../x.py\na\n=======\nb\n>>>>>>> REPLACE"
    tst = "<<<<<<< SEARCH tests/test_repro.py\nassert\n=======\nb\n>>>>>>> REPLACE"
    fake = Fake()
    r, p = go(repo, fake, proposals=[bad, esc, tst])
    assert r.outcome == "REJECTED" and len(p) == 3 and r.patch_sha256 is None
    assert "hidden" not in fake.calls
    r, _ = go(repo, Fake(), proposals=["NO_PATCH"])
    assert r.outcome == "NO_PATCH"


def test_literal_special_case_rejected_in_loop(repo):
    special = (
        "<<<<<<< SEARCH shop.py\n    return price - price * pct\n=======\n"
        "    if price == 200:\n        return 180\n    return price - price * pct\n>>>>>>> REPLACE"
    )
    path, sha = repo
    r, _ = go(
        repo,
        Fake(visible_ok=True),
        proposals=[special] * 3,
        visible_test_sources=["def test_a():\n    assert discount(200, 10) == 180\n"],
    )
    assert r.outcome == "REJECTED" and r.reason == "test_literal:shop.py"


def test_diff_that_does_not_apply_is_a_failed_attempt_not_a_crash(repo, monkeypatch):
    from contextlib import contextmanager

    from traceforge.repair import loop
    from traceforge.repair.worktree import WorktreeError

    real = loop.worktree

    @contextmanager
    def broken(repo_path, base_sha, diff=None, **k):
        if diff:  # only applying a diff fails; the clean baseline worktree still works
            raise WorktreeError("git apply failed: patch does not apply")
        with real(repo_path, base_sha, **k) as wt:
            yield wt

    monkeypatch.setattr(loop, "worktree", broken)
    fake = Fake()
    r, p = go(repo, fake, proposals=[CORRECT] * 3)
    assert r.outcome == "REJECTED" and len(p) == 3 and r.patch_sha256 is None
    assert all(a.reasons == ["patch_does_not_apply"] for a in r.attempts)
    assert "hidden" not in fake.calls


def test_lf_diff_applies_to_lf_file_regardless_of_platform_newlines(repo):
    """Regression: git apply input must not be newline-translated (broke on Windows)."""
    path, sha = repo
    r, _ = go(repo, real_runner, proposals=[CORRECT])
    assert r.attempts[0].reasons == [] and r.diff and "\r" not in r.diff
    with worktree(path, sha, r.diff) as wt:
        assert (wt / "shop.py").exists()
