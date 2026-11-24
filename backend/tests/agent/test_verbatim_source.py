# ruff: noqa: E501
"""The patch prompt carries the real text of the target file, so SEARCH blocks can match it."""

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace as N

import pytest
from agentfakes import SUBMIT_CFG, FakeChat, resp

sys.path.insert(0, str(Path(__file__).parents[1] / "repair"))
from gitrepo import make_repo, pytest_runner  # noqa: E402

from traceforge.agent import patch, prompting
from traceforge.agent.diagnose import Usage
from traceforge.agent.pipeline import Sources, sample_sources
from traceforge.agent.repair_run import run_case_with_repair
from traceforge.agent.tools import SubmitDiagnosis, ToolContext
from traceforge.config import Settings
from traceforge.contracts.test_run import TestRunResult
from traceforge.retrieval import RealContextSource

SETTINGS_PY = 'class Settings:\n    db_host: str = "localhost"\n    redis_host: str = "redis-broker.internal"\n    redis_port: int = 6379\n'
SERVICE = "shop_api"
SETTINGS = f"lab/{SERVICE}/app/settings.py"
HIDDEN = "HIDDEN_MARK_zz"
FILES = {
    SETTINGS: SETTINGS_PY,
    f"lab/{SERVICE}/app/other.py": "X = 1\n",
    f"lab/{SERVICE}/tests/test_visible.py": "def test_v():\n    assert True\n",
    "lab/worker/app/settings.py": 'redis_host = "worker-only"\n',
    "datasets/hidden_tests/shop_api-001/test_h.py": f"def test_{HIDDEN}(): pass\n",
    f"lab/{SERVICE}/app/secrets.env": "TOKEN=abc\n",
    "tests/test_repro.py": "from pathlib import Path\n\n\ndef test_a():\n    p = Path(__file__).parents[1] / 'lab/shop_api/app/settings.py'\n    assert 'lab_redis' in p.read_text()\n",
    "tests/test_visible.py": "def test_v():\n    assert True\n",
    "tests/test_hidden.py": f"def test_{HIDDEN}():\n    assert True\n",
}
CASE = N(service=SERVICE, case_id="shop_api-001")
DIAG = SubmitDiagnosis(
    cause_class="configuration",
    config_key="shop_api.REDIS_HOST",
    supporting_evidence_ids=["EV-0001"],
    rationale="bad default",
)
RENDERED = "settings.redis_host [str] = 'redis-broker.internal'"


def evidence(path=SETTINGS):
    item = N(id="EV-0001", kind="config", service=SERVICE, content=RENDERED, path=path)
    return N(items=[item])


@pytest.fixture
def repo(tmp_path):
    path, sha = make_repo(tmp_path / "r", FILES)
    return Path(path), sha


def tc_for(repo_path):
    return ToolContext(CASE, evidence(), RealContextSource(repo_path))


# --- the source reader: exact text, strictly limited ---------------------------------------------


def test_read_file_returns_exact_bytes_including_crlf(repo):
    p = repo[0] / SETTINGS
    p.write_bytes(b'a = 1\r\nb = "x"\r\n')
    assert RealContextSource(repo[0]).read_file(CASE, SETTINGS) == 'a = 1\r\nb = "x"\r\n'


@pytest.mark.parametrize(
    "path",
    [
        "lab/shop_api/tests/test_visible.py",  # tests
        "lab/worker/app/settings.py",  # another service
        "lab/shop_api/app/secrets.env",  # not an editable source suffix
        "lab/shop_api/../worker/app/settings.py",  # traversal
        "datasets/hidden_tests/shop_api-001/test_h.py",  # hidden tests
        "tests/test_hidden.py",
        "lab/shop_api/app/missing.py",
        "C:/Windows/win.ini",
    ],
)
def test_read_file_refuses_everything_that_is_not_an_editable_source_file(repo, path):
    assert RealContextSource(repo[0]).read_file(CASE, path) is None


def test_source_files_lists_only_editable_files_of_the_service(repo):
    assert RealContextSource(repo[0]).source_files(CASE) == [
        f"lab/{SERVICE}/app/other.py",
        SETTINGS,
    ]


# --- the prompt: real file text, clearly separated from rendered evidence -------------------------


def test_target_section_is_the_verbatim_file_not_the_rendered_evidence_line(repo):
    code = patch._code(tc_for(repo[0]), DIAG)
    assert f'<source_file path="{SETTINGS}">\n{SETTINGS_PY}</source_file>' in code
    assert RENDERED not in code and "other.py" not in code  # does not mention the name
    assert "worker-only" not in code and HIDDEN not in code and "TOKEN" not in code


def test_whole_prompt_labels_what_is_file_text_and_what_is_evidence(repo):
    chat = FakeChat(resp(content="NO_PATCH"))
    ctx = tc_for(repo[0])
    ctx.evidence.items.append(
        N(id="EV-0002", kind="log", service=SERVICE, content="ConnectionError redis", path=None)
    )
    ctx.evidence.items[0].sha256 = "0" * 64
    ctx.evidence.items[1].sha256 = "1" * 64
    ctx.evidence.items[0].ts = ctx.evidence.items[1].ts = None
    patch.ask_patch(ctx, DIAG, chat, Usage(), None)
    system, text = chat.messages[0][0]["content"], chat.messages[0][1]["content"]
    assert "Only text inside <source_file> blocks is real file content" in system
    assert text.index("<source_file") < text.index("<evidence>")
    assert RENDERED in text.split("<evidence>\n")[-1]  # evidence stays, as evidence only


def test_large_file_is_shown_only_around_the_target_with_exact_lines(repo):
    filler = "".join(f"line_{i} = {i}\n" for i in range(900))
    big = filler + 'redis_host = "redis-broker.internal"\n' + filler
    (repo[0] / SETTINGS).write_text(big, newline="\n")
    code = patch._code(tc_for(repo[0]), DIAG)
    assert len(big) > patch.FILE_CHARS and len(code) < patch.FILE_CHARS
    m = re.search(
        r'<source_file path="[^"]+" lines="(\d+)-(\d+)">\n(.*?)</source_file>', code, re.S
    )
    a, b = int(m[1]), int(m[2])
    assert m[3] == "".join(big.splitlines(keepends=True)[a - 1 : b])  # contiguous, exact
    assert 'redis_host = "redis-broker.internal"' in m[3]


def test_cited_evidence_path_is_used_even_when_the_name_is_not_in_the_file(repo):
    (repo[0] / "lab/shop_api/app/other.py").write_text("HOST = 'h'\n")
    diag = DIAG.model_copy(update={"config_key": "shop_api.NOWHERE"})
    ctx = ToolContext(CASE, evidence("lab/shop_api/app/other.py"), RealContextSource(repo[0]))
    assert 'path="lab/shop_api/app/other.py"' in patch._code(ctx, diag)


def test_at_most_two_files_are_shown(repo):
    for n in "abc":
        (repo[0] / f"lab/shop_api/app/{n}.py").write_text("redis_host = 1\n")
    code = patch._code(tc_for(repo[0]), DIAG)
    assert code.count("<source_file path=") == patch.MAX_FILES


def test_context_without_file_access_keeps_the_old_target_section():
    s = sample_sources()
    tc = ToolContext(CASE, evidence(), s.context)
    assert RENDERED in patch._code(tc, DIAG)  # fallback only for sources that cannot read files


def test_prompt_hash_covers_the_new_template():
    assert "patch_v4" in prompting.VERSIONS
    assert "<source_file>" in prompting.load("patch_v4")[0]


# --- end to end: SEARCH copied from the prompt applies, tests run, feedback follows -------------


def edit(old, new, path=SETTINGS):
    return f"<<<<<<< SEARCH {path}\n{old}\n=======\n{new}\n>>>>>>> REPLACE"


class Runner:
    def __init__(self, fail_visible=False):
        self.calls, self.fail_visible = [], fail_visible

    def __call__(self, req):
        self.calls.append(req.suite)
        if self.fail_visible and req.suite != "hidden":
            return TestRunResult(
                passed=0, failed=1, tests=[], stdout_tail="VISIBLE_OUT assert 'a' == 'b'",
                duration_ms=1, timed_out=False,
            )  # fmt: skip
        return pytest_runner(req)


def run(repo, chat, cond, runner, allow=(SETTINGS,)):
    s = sample_sources()
    src = Sources(s.cases, s.evidence, RealContextSource(repo[0]))
    case = s.cases.get("config")
    case = case.model_copy(update={"service": SERVICE})
    return run_case_with_repair(
        case, cond, _with_case(src, case), repo_path=str(repo[0]), base_sha=repo[1], run_tests=runner,
        allowlist=list(allow), visible_test_sources=[FILES["tests/test_visible.py"]], chat_fn=chat,
        settings=Settings(),
    )  # fmt: skip


def _with_case(src, case):
    class Cases:
        sha256 = "0" * 64

        def get(self, _id):
            return case

    return Sources(Cases(), src.evidence, src.context)


def test_search_text_copied_from_the_prompt_matches_and_visible_tests_run(repo):
    old = 'redis_host: str = "redis-broker.internal"'
    chat = FakeChat(resp(SUBMIT_CFG), resp(content=edit(old, 'redis_host: str = "lab_redis"')))
    runner = Runner()
    rec = run(repo, chat, "L1", runner)
    prompt = chat.messages[1][1]["content"]
    assert old in prompt and "<source_file" in prompt and HIDDEN not in json.dumps(chat.messages)
    assert rec.attempts == 1  # the edit applied (no no_match)
    assert runner.calls[:3] == ["reproducer", "reproducer", "visible"]  # visible suite ran


def test_search_text_copied_from_the_rendered_evidence_still_fails_as_no_match(repo):
    chat = FakeChat(resp(SUBMIT_CFG), *[resp(content=edit(RENDERED, "x"))] * 3)
    rec = run(repo, chat, "L0", Runner())
    assert rec.outcome == "REJECTED" and rec.failure_reason == "no_match" and rec.attempts == 3


def test_edit_outside_the_allowed_files_is_rejected_before_any_test(repo):
    other = f"lab/{SERVICE}/app/other.py"
    chat = FakeChat(resp(SUBMIT_CFG), *[resp(content=edit("X = 1", "X = 2", other))] * 3)
    runner = Runner()
    rec = run(repo, chat, "L0", runner, allow=(SETTINGS,))
    assert rec.outcome == "REJECTED" and "visible" not in runner.calls


def test_f1_second_attempt_gets_the_real_visible_output_and_is_a_new_request(repo):
    from traceforge.evaluation.real_run import request_recorder

    old = 'redis_host: str = "redis-broker.internal"'
    bad = edit(old, 'redis_host: str = "still-wrong"')
    log = []
    chat = request_recorder(FakeChat(resp(SUBMIT_CFG), *[resp(content=bad)] * 3), log)
    runner = Runner(fail_visible=True)
    rec = run(repo, chat, "L1", runner)
    patch_rows = [r for r in log if r["stage"] == "patch"]
    assert rec.attempts == 3 and runner.calls.count("visible") == 3
    assert [r["has_feedback"] for r in patch_rows] == [False, True, True]
    assert "VISIBLE_OUT assert 'a' == 'b'" in patch_rows[1]["feedback"]
    assert [r["attempt_index"] for r in patch_rows] == [0, 1, 2]
    assert HIDDEN not in json.dumps(log)


def test_f0_attempts_never_receive_feedback_but_are_separate_attempts(repo):
    from traceforge.evaluation.real_run import request_recorder

    old = 'redis_host: str = "redis-broker.internal"'
    bad = edit(old, 'redis_host: str = "still-wrong"')
    log = []
    chat = request_recorder(FakeChat(resp(SUBMIT_CFG), *[resp(content=bad)] * 3), log)
    run(repo, chat, "L0", Runner(fail_visible=True))
    patch_rows = [r for r in log if r["stage"] == "patch"]
    assert not any(r["has_feedback"] for r in patch_rows)
    assert [r["attempt_index"] for r in patch_rows] == [0, 1, 2]


def test_each_attempt_records_counts_and_has_its_own_diff(repo):
    old = 'redis_host: str = "redis-broker.internal"'
    rec = None
    chat = FakeChat(resp(SUBMIT_CFG), *[resp(content=edit(old, 'redis_host: str = "w"'))] * 3)
    art = {}
    s = sample_sources()
    case = s.cases.get("config").model_copy(update={"service": SERVICE})
    rec = run_case_with_repair(
        case, "L1", _with_case(Sources(s.cases, s.evidence, RealContextSource(repo[0])), case),
        repo_path=str(repo[0]), base_sha=repo[1], run_tests=Runner(fail_visible=True),
        allowlist=[SETTINGS], visible_test_sources=[], chat_fn=chat, settings=Settings(),
        artifacts=art,
    )  # fmt: skip
    atts = art["repair"].attempts
    assert rec.attempts == 3 and all(a.diff and a.counts for a in atts)
    assert atts[0].counts["visible_failed"] == 1 and atts[0].counts["visible_passed"] == 0
