"""Real-container tests. Needs Docker; one container at a time."""

import subprocess

import pytest
from conftest import add_probe, docker_up

from traceforge.contracts.test_run import TestRunRequest
from traceforge.sandbox import make_run_tests
from traceforge.sandbox.runner import HIDDEN_WITHHELD, run_tests

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(not docker_up(), reason="Docker daemon not available"),
]


def req(wt, suite="visible", t=60):
    return TestRunRequest(case_id="case1", worktree_path=str(wt), suite=suite, timeout_s=t)


def leftovers() -> str:
    p = subprocess.run(
        ["docker", "ps", "-a", "-q", "--filter", "name=tf-sbx-"], capture_output=True, text=True
    )
    return p.stdout.strip()


@pytest.fixture(autouse=True)
def no_container_left_behind():
    yield
    assert leftovers() == ""


def test_visible_passes_and_skips_integration(worktree):
    r = run_tests(req(worktree))
    assert r.error is None and not r.timed_out
    assert (r.passed, r.failed) == (2, 0)
    assert {t.id for t in r.tests} == {
        "tests/test_ok.py::test_ident",
        "tests/test_ok.py::TestGroup::test_ident_str",
    }
    assert r.duration_ms > 0 and len(r.stdout_tail) <= 4096


def test_reproducer_fails_on_buggy_code(worktree):
    r = run_tests(req(worktree, "reproducer"))
    assert r.error is None and (r.passed, r.failed) == (0, 1)
    assert r.tests[0].id == "reproducer/test_repro.py::test_add" and r.tests[0].outcome == "failed"
    assert "assert" in r.stdout_tail


def test_fixed_code_passes_all_suites(worktree, hidden_root):
    (worktree / "shop.py").write_text(
        "def add(a, b):\n    return a + b\n\n\ndef ident(x):\n    return x\n"
    )
    run = make_run_tests(worktree.parent, hidden_dir=hidden_root)
    assert run(req(worktree, "reproducer")).passed == 1
    h = run(req(worktree, "hidden"))
    assert h.error is None and (h.passed, h.failed) == (2, 0)
    assert {t.id for t in h.tests} == {
        "test_hidden.py::test_hidden_add",
        "test_hidden.py::test_hidden_zero",
    }


def test_hidden_fails_on_buggy_and_output_withheld(worktree, hidden_root):
    h = make_run_tests(worktree.parent, hidden_dir=hidden_root)(req(worktree, "hidden"))
    assert h.failed == 1 and h.passed == 1  # add(0,0)==0 passes even when buggy
    assert h.stdout_tail == HIDDEN_WITHHELD  # no hidden assertion text can reach a prompt


def test_relative_worktree_path_resolved_under_repo(worktree, hidden_root):
    run = make_run_tests(worktree.parent)
    r = run(TestRunRequest(case_id="case1", worktree_path="wt", suite="visible", timeout_s=60))
    assert r.error is None and r.passed == 2


def test_hidden_never_visible_in_visible_run(worktree):
    add_probe(worktree, "test_hidden_absent.py")
    r = run_tests(req(worktree, "reproducer"))  # runs reproducer/ incl. the absent-check probe
    probe = [t for t in r.tests if t.id.endswith("test_hidden_dir_not_mounted")]
    assert probe and probe[0].outcome == "passed"


def test_network_is_really_off(worktree):
    add_probe(worktree, "test_network.py")
    r = run_tests(req(worktree, "reproducer"))
    probes = {t.id.split("::")[-1]: t.outcome for t in r.tests if "test_network" in t.id}
    assert probes == {"test_network_is_off": "passed", "test_dns_is_off": "passed"}, r.stdout_tail


def test_fs_readonly_no_socket_no_host_no_secrets(worktree):
    add_probe(worktree, "test_fs.py")
    r = run_tests(req(worktree, "reproducer"))
    probes = {t.id.split("::")[-1]: t.outcome for t in r.tests if "test_fs" in t.id}
    assert len(probes) == 4 and set(probes.values()) == {"passed"}, r.stdout_tail
    assert not (worktree / "evil.txt").exists()  # nothing leaked to the host worktree


def test_fork_bomb_capped_by_pids_limit(worktree):
    add_probe(worktree, "test_forkbomb.py")
    r = run_tests(req(worktree, "reproducer", t=60))
    assert r.error is None and not r.timed_out and r.passed == 1, r.stdout_tail


def test_memory_hog_is_killed(worktree):
    add_probe(worktree, "test_memhog.py")
    r = run_tests(req(worktree, "reproducer", t=60))
    assert r.passed == 0 and (r.error or r.failed), "memory hog must never succeed"
    assert r.error and "OOM" in r.error or "no test report" in r.error


def test_infinite_loop_timeout_forced_kill(worktree):
    add_probe(worktree, "test_loop.py")
    r = run_tests(req(worktree, "reproducer", t=5))
    assert r.timed_out is True and r.passed == 0 and 5000 <= r.duration_ms < 20000


def test_worktree_hidden_overlap_refused(worktree):
    (worktree / "hid" / "case1").mkdir(parents=True)  # hidden dir inside the model-visible tree
    r = run_tests(req(worktree, "hidden"), hidden_dir=worktree / "hid")
    assert r.error and "overlaps" in r.error
