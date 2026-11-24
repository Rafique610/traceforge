# ruff: noqa: E501
import json
import sys
from pathlib import Path

import pytest
from agentfakes import PROVIDER_DOWN, SUBMIT_CFG, SUBMIT_CODE, FakeChat, call, resp

sys.path.insert(0, str(Path(__file__).parents[1] / "repair"))
from gitrepo import make_repo, pytest_runner  # noqa: E402

from traceforge.agent.pipeline import Sources, sample_sources
from traceforge.agent.repair_run import run_case_with_repair
from traceforge.agent.sources import SampleContextSource
from traceforge.config import Settings
from traceforge.contracts.agent_run import AgentRunRecord
from traceforge.contracts.test_run import TestRunResult
from traceforge.incidents import service
from traceforge.incidents.models import AuditEvent
from traceforge.incidents.schemas import IncidentCreate
from traceforge.incidents.states import State

HIDDEN = "HIDDEN_MARK_zz"
CODE_FILES = {
    "shop.py": "def discount(price, pct):\n    return price - price * pct\n",
    "tests/test_repro.py": "from shop import discount\n\n\ndef test_a():\n    assert discount(200, 10) == 180\n",
    "tests/test_visible.py": "from shop import discount\n\n\ndef test_zero():\n    assert discount(100, 0) == 100\n",
    "tests/test_hidden.py": f"from shop import discount\n\n\ndef test_{HIDDEN}():\n    assert discount(50, 50) == 25\n",
}
CFG_FILES = {
    "config.ini": "host=reddis\n",
    "app.py": "def host():\n    return open('config.ini').read().split('=')[1].strip()\n",
    "tests/test_repro.py": "from app import host\n\n\ndef test_a():\n    assert host() == 'redis'\n",
    "tests/test_visible.py": "from app import host\n\n\ndef test_v():\n    assert host()\n",
    "tests/test_hidden.py": f"from app import host\n\n\ndef test_{HIDDEN}():\n    assert host().startswith('red')\n",
}


def edit(path, old, new):
    return f"<<<<<<< SEARCH {path}\n{old}\n=======\n{new}\n>>>>>>> REPLACE"


FIX_CODE = edit("shop.py", "    return price - price * pct", "    return price - price * pct / 100")
BAD_CODE = edit("shop.py", "    return price - price * pct", "    return price - pct")
FIX_CFG = edit("config.ini", "host=reddis", "host=redis")


class Ctx(SampleContextSource):
    def read_symbol(self, case, path, qualname):
        return "def discount(price, pct):\n    return price - price * pct"


def sources():
    s = sample_sources()
    return Sources(s.cases, s.evidence, Ctx())


class Runner:
    def __init__(self, fail_suite=None):
        self.calls, self.fail_suite = [], fail_suite

    def __call__(self, req):
        self.calls.append(req.suite)
        if req.suite == self.fail_suite:
            return TestRunResult(
                passed=0,
                failed=0,
                tests=[],
                stdout_tail="",
                duration_ms=1,
                timed_out=False,
                error="down",
            )
        return pytest_runner(req)


def stub_runner(req):
    """Cheap scripted runner: everything fails on the patched tree (equal-attempts tests)."""
    bad = dict(
        passed=0, failed=1, tests=[], stdout_tail="VISIBLE FAIL", duration_ms=1, timed_out=False
    )
    return TestRunResult(**bad)


def go(tmp_path, files, alias, chat, cond="L0", allow=("shop.py",), runner=None, inc=None, db=None):
    path, sha = make_repo(tmp_path / "r", files)
    case = inc or sources().cases.get(alias)
    runner = runner or Runner()
    rec = run_case_with_repair(
        case, cond, sources(), repo_path=path, base_sha=sha, run_tests=runner, allowlist=list(allow),
        visible_test_sources=[files["tests/test_visible.py"]], chat_fn=chat, settings=Settings(), db=db,
    )  # fmt: skip
    AgentRunRecord.model_validate(rec.model_dump())
    return rec, runner


def no_hidden_leak(chat):
    text = json.dumps(chat.messages)
    assert HIDDEN not in text and "hidden" not in text.lower()


def test_code_fix_verified(tmp_path):
    chat = FakeChat(resp(SUBMIT_CODE), resp(content=FIX_CODE))
    rec, _ = go(tmp_path, CODE_FILES, "code", chat, "G0")
    assert rec.outcome == "TEST_VERIFIED_IN_LAB" and rec.hidden_passed is True
    assert rec.attempts == 1 and rec.patch_sha256 and rec.condition == "G0"
    assert "SEARCH" in chat.messages[1][0]["content"]
    no_hidden_leak(chat)


def test_config_fix_verified(tmp_path):
    chat = FakeChat(resp(SUBMIT_CFG), resp(content=FIX_CFG))
    rec, _ = go(tmp_path, CFG_FILES, "config", chat, "L1", allow=["config.ini"])
    assert rec.outcome == "TEST_VERIFIED_IN_LAB" and rec.attempts == 1
    no_hidden_leak(chat)


def test_wrong_patch_rejected(tmp_path):
    chat = FakeChat(resp(SUBMIT_CODE), *[resp(content=BAD_CODE)] * 3)
    rec, _ = go(tmp_path, CODE_FILES, "code", chat)
    assert (rec.outcome, rec.attempts) == ("REJECTED", 3)
    assert (
        rec.failure_reason == "visible_failed" and rec.hidden_passed is False and rec.patch_sha256
    )


def test_f0_f1_equal_attempts_and_feedback(tmp_path):
    chats = {}
    for cond in ("L0", "L1"):
        chats[cond] = FakeChat(resp(SUBMIT_CODE), *[resp(content=BAD_CODE)] * 3)
        rec, _ = go(tmp_path / cond, CODE_FILES, "code", chats[cond], cond, runner=stub_runner)
        assert rec.attempts == 3
        no_hidden_leak(chats[cond])
    assert chats["L0"].n == chats["L1"].n == 4
    tag = "visible_test_feedback"
    assert all(tag not in m[1]["content"] for m in chats["L0"].messages[1:])
    f1 = [m[1]["content"] for m in chats["L1"].messages[1:]]
    assert tag not in f1[0] and tag in f1[1] and tag in f1[2]


def test_sandbox_error_unverified(tmp_path):
    chat = FakeChat(resp(SUBMIT_CODE), resp(content=FIX_CODE))
    rec, _ = go(tmp_path, CODE_FILES, "code", chat, runner=Runner(fail_suite="reproducer"))
    assert rec.outcome == "UNVERIFIED" and rec.failure_reason == "sandbox_error"


@pytest.mark.parametrize("cls", ["insufficient_evidence", "runtime_dependency"])
def test_abstain_and_runtime_make_no_repair_call(tmp_path, cls):
    sub = call("submit_diagnosis", cause_class=cls, supporting_evidence_ids=["EV-0005"])
    if cls == "insufficient_evidence":
        sub = call("submit_diagnosis", cause_class=cls)
    chat = FakeChat(resp(sub))
    rec, runner = go(
        tmp_path, CODE_FILES, "config" if cls == "runtime_dependency" else "abstain", chat
    )
    assert rec.outcome == "NO_PATCH" and rec.patch_sha256 is None and rec.attempts == 0
    assert runner.calls == [] and chat.n == 1


def test_provider_error_is_no_patch(tmp_path):
    chat = FakeChat(resp(SUBMIT_CODE), PROVIDER_DOWN)
    rec, _ = go(tmp_path, CODE_FILES, "code", chat)
    assert rec.outcome == "NO_PATCH" and rec.failure_reason.startswith("provider_error")


@pytest.mark.parametrize(
    ("patch", "mid"), [(FIX_CODE, State.VERIFIED), (BAD_CODE, State.UNVERIFIED)]
)
def test_incident_states(tmp_path, db, patch, mid):
    case = sources().cases.get("code")
    inc = service.create_incident(db, IncidentCreate(case_id=case.case_id, service="shop_api"))
    go(
        tmp_path,
        CODE_FILES,
        "code",
        FakeChat(resp(SUBMIT_CODE), *[resp(content=patch)] * 3),
        inc=inc,
        db=db,
    )
    db.refresh(inc)
    assert inc.state == State.REVIEW_PENDING
    states = [
        e.to_state
        for e in db.query(AuditEvent).filter_by(incident_id=inc.id).order_by(AuditEvent.id)
    ]
    assert states[-4:] == [State.PATCH_PROPOSED, State.VALIDATING, mid, State.REVIEW_PENDING]


@pytest.mark.parametrize("cond", ["L0", "L1"])
def test_every_patch_attempt_carries_its_own_attempt_index(tmp_path, cond):
    chat = FakeChat(resp(SUBMIT_CODE), *[resp(content=BAD_CODE)] * 3)
    rec, _ = go(tmp_path, CODE_FILES, "code", chat, cond, runner=stub_runner)
    assert rec.attempts == 3
    assert [k.get("attempt_index") for k in chat.kw] == [
        None,
        None,
        1,
        2,
    ]  # diagnose, 1st, 2nd, 3rd


def test_f1_feedback_reaches_second_attempt_and_is_visible_output_only(tmp_path):
    from traceforge.evaluation.real_run import request_recorder

    chat, log = FakeChat(resp(SUBMIT_CODE), *[resp(content=BAD_CODE)] * 3), []
    rec, _ = go(tmp_path, CODE_FILES, "code", request_recorder(chat, log), "L1", runner=stub_runner)
    patch = [r for r in log if r["stage"] == "patch"]
    assert [r["has_feedback"] for r in patch] == [False, True, True]
    assert "VISIBLE FAIL" in patch[1]["feedback"] and HIDDEN not in json.dumps(log)
    assert patch[0]["messages_sha256"] != patch[1]["messages_sha256"]  # inputs really differ
    assert rec.attempts == 3


def test_f0_attempts_after_the_first_are_flagged_as_new_requests_with_identical_prompt(tmp_path):
    from traceforge.evaluation.real_run import request_recorder

    chat, log = FakeChat(resp(SUBMIT_CODE), *[resp(content=BAD_CODE)] * 3), []
    go(tmp_path, CODE_FILES, "code", request_recorder(chat, log), "L0", runner=stub_runner)
    patch = [r for r in log if r["stage"] == "patch"]
    assert [r["attempt_index"] for r in patch] == [0, 1, 2]
    assert len({r["messages_sha256"] for r in patch}) == 1  # F0: same prompt, distinct attempts
    assert not any(r["has_feedback"] for r in patch)


def test_f1_without_visible_run_gets_no_feedback_documented_limit(tmp_path):
    """Edits that never apply (no_match) produce no visible-test output, so F1 sends nothing new.
    This is the current design (feedback = visible test output), recorded as a limit, not a fix."""
    from traceforge.evaluation.real_run import request_recorder

    miss = edit("shop.py", "    return NOT_IN_FILE", "    return 0")
    chat, log = FakeChat(resp(SUBMIT_CODE), *[resp(content=miss)] * 3), []
    rec, _ = go(tmp_path, CODE_FILES, "code", request_recorder(chat, log), "L1")
    assert rec.attempts == 3 and not any(r["has_feedback"] for r in log)


def test_truncated_patch_reply_is_a_recorded_no_patch_not_a_provider_outage(tmp_path):
    from traceforge.agent.gateway import OutputTruncated

    chat = FakeChat(resp(SUBMIT_CODE), OutputTruncated("patch reply truncated"))
    rec, _ = go(tmp_path, CODE_FILES, "code", chat)
    assert rec.outcome == "NO_PATCH" and rec.failure_reason == "output_truncated"
    assert not (rec.failure_reason or "").startswith("provider_error")  # so the run keeps a record


def test_real_provider_failure_in_a_patch_attempt_is_still_a_provider_error(tmp_path):
    chat = FakeChat(resp(SUBMIT_CODE), PROVIDER_DOWN)
    rec, _ = go(tmp_path, CODE_FILES, "code", chat)
    assert (rec.failure_reason or "").startswith("provider_error")


def test_patch_requests_use_the_uniform_output_cap():
    from traceforge.agent.patch import PATCH_MAX_OUTPUT_TOKENS

    assert PATCH_MAX_OUTPUT_TOKENS == 8192


def test_v4_second_attempt_prompt_keeps_original_feedback_text(tmp_path):
    chat = FakeChat(resp(SUBMIT_CODE), *[resp(content=BAD_CODE)] * 3)
    path, sha = make_repo(tmp_path / "r", CODE_FILES)
    rec = run_case_with_repair(
        sources().cases.get("code"), "L1", sources(), repo_path=path, base_sha=sha,
        run_tests=stub_runner, allowlist=["shop.py"], chat_fn=chat, settings=Settings(),
        visible_test_sources=[CODE_FILES["tests/test_visible.py"]], pipeline="v4",
    )  # fmt: skip
    assert rec.attempts == 3
    second = chat.messages[2][1]["content"]
    assert "<visible_test_feedback>" in second and "VISIBLE FAIL" in second
    assert "your previous edit" not in second and "did not make the visible tests" not in second
    no_hidden_leak(chat)
