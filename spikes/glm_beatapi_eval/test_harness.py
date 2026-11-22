"""Unit tests for the eval harness itself.

TEST DOUBLES: every `chat` below is a scripted fake (FakeChat), not the model. Nothing here sends a
network request; the sandbox runner is replaced by a stub where the code path would call Docker."""

import json
from types import SimpleNamespace

import pytest

import agent_loop
import scoring
import tools
import usage_guard
import worktree
from traceforge.agent.gateway import GatewayError, ModelResponse, ToolCall

TASK = {"id": "TX", "ask": "diagnose and fix", "bug_report": "it is broken"}


def resp(*calls, content=None, finish="tool_calls", cache_hit=False):
    return ModelResponse(
        content=content, tool_calls=[ToolCall(name=n, arguments=json.dumps(a)) for n, a in calls],
        tokens_in=10, tokens_out=5, latency_ms=1.0, provider="p", model="m",
        finish_reason=finish, cache_hit=cache_hit)


class FakeChat:  # test double
    def __init__(self, *script):
        self.script, self.calls = list(script), 0

    def __call__(self, messages, tool_schemas):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "backend/traceforge/pkg").mkdir(parents=True)
    (tmp_path / "backend/tests").mkdir(parents=True)
    (tmp_path / "backend/traceforge/pkg/mod.py").write_bytes(b"def f():\r\n    return 1\r\n")
    (tmp_path / "backend/tests/test_a.py").write_text("def test_a():\n    assert True\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/secret.md").write_text("fix is X")
    return tmp_path


def stub_sandbox(root, paths):
    return {"passed": 1, "failed": 0, "tests": [], "tail": "ok", "error": None, "timed_out": False}


def box(tree, **kw):
    return tools.Toolbox(tree, sandbox=stub_sandbox, **kw)


# --- tool dispatch ------------------------------------------------------------------------
def test_dispatch_read_list_grep_and_categories(tree):
    tb = box(tree)
    assert tb.dispatch("list_dir", '{"path": "backend/traceforge/pkg"}') == ("ok", "mod.py")
    cat, text = tb.dispatch("read_file", '{"path": "backend/traceforge/pkg/mod.py"}')
    assert cat == "ok" and "2:     return 1" in text
    assert tb.dispatch("grep", '{"pattern": "return", "path": "backend/traceforge"}')[0] == "ok"
    assert tb.dispatch("nope", "{}")[0] == "unknown_tool"
    assert tb.dispatch("read_file", "{not json")[0] == "bad_args"
    assert tb.dispatch("read_file", '{"wrong": 1}')[0] == "bad_args"
    assert tb.dispatch("grep", '{"pattern": "(", "path": "backend/traceforge"}')[0] == "tool_error"
    assert tb.dispatch("run_tests", '{"paths": ["tests"]}')[0] == "ok"
    assert tb.dispatch("run_tests", '{"paths": ["../x"]}')[0] == "tool_error"


# --- edit policy --------------------------------------------------------------------------
@pytest.mark.parametrize("path", [
    ".git/config", "docs/secret.md", "backend/docs/x.py", "/etc/passwd", "C:/x.py",
    "backend/traceforge/../../docs/secret.md", "backend/pyproject.toml", "backend/tests/test_zz_hidden.py",
])
def test_edit_policy_refuses_forbidden_paths(tree, path):
    tb = box(tree, hidden_names={"backend/tests/hidden_secret.py"})
    cat, text = tb.dispatch("apply_edit", json.dumps({"path": path, "search": "a", "replace": "b"}))
    assert cat == "tool_error" and "ERROR" in text
    cat, _ = tb.dispatch("apply_edit", json.dumps({"path": path, "search": "", "replace": "x=1"}))
    assert cat == "tool_error"
    assert tb.dispatch("read_file", json.dumps({"path": path}))[0] == "tool_error"


def test_edit_policy_refuses_declared_hidden_test_path(tree):
    tb = box(tree, hidden_names={"backend/tests/hidden_secret.py"})
    cat, _ = tb.dispatch("apply_edit", json.dumps(
        {"path": "backend/tests/hidden_secret.py", "search": "", "replace": "x"}))
    assert cat == "tool_error"


def test_edit_exactly_once_preserves_crlf_and_new_test_file(tree):
    tb = box(tree)
    f = tree / "backend/traceforge/pkg/mod.py"
    assert tb.dispatch("apply_edit", json.dumps(
        {"path": "backend/traceforge/pkg/mod.py", "search": "return 1", "replace": "return 2"}))[0] == "ok"
    assert f.read_bytes() == b"def f():\r\n    return 2\r\n"
    assert tb.dispatch("apply_edit", json.dumps(
        {"path": "backend/traceforge/pkg/mod.py", "search": "zzz", "replace": "q"}))[0] == "tool_error"
    f.write_bytes(b"a = 1\na = 1\n")
    cat, text = tb.dispatch("apply_edit", json.dumps(
        {"path": "backend/traceforge/pkg/mod.py", "search": "a = 1", "replace": "b"}))
    assert cat == "tool_error" and "2 times" in text
    new = {"path": "backend/tests/test_new.py", "search": "", "replace": "def test_x():\n    pass\n"}
    assert tb.dispatch("apply_edit", json.dumps(new))[0] == "ok"
    assert tb.dispatch("apply_edit", json.dumps(new))[0] == "tool_error"  # already exists
    src_new = {"path": "backend/traceforge/pkg/new.py", "search": "", "replace": "x=1"}
    assert tb.dispatch("apply_edit", json.dumps(src_new))[0] == "tool_error"  # new src file refused
    assert tb.files_created == {"backend/tests/test_new.py"}


# --- loop: cap, stop-on-error, submit -----------------------------------------------------
def test_request_cap_ends_without_submit(tree):
    chat = FakeChat(*[resp(("list_dir", {"path": "backend"})) for _ in range(5)])
    rec = agent_loop.run_agent(TASK, box(tree), chat, max_requests=3)
    assert chat.calls == 3 and rec["requests"] == 3 and rec["submitted"] is None
    assert rec["stats"]["no_submit"] == 1
    last_tool_msgs = rec["steps"][1]["calls"][0]["result"]
    assert "backend" in last_tool_msgs or "traceforge" in last_tool_msgs


def test_submit_ends_loop_and_malformed_submit_is_counted(tree):
    chat = FakeChat(
        resp(("submit_final", {"diagnosis": "x"})),
        resp(("submit_final", {"diagnosis": "d", "root_cause_file": "f", "summary": "s"})),
    )
    rec = agent_loop.run_agent(TASK, box(tree), chat)
    assert chat.calls == 2 and rec["submitted"]["summary"] == "s"
    assert rec["stats"]["tool_bad_args"] == 1


def test_stop_on_gateway_error_no_retry(tree, tmp_path):
    saved = []
    chat = FakeChat(resp(("list_dir", {"path": "backend"})), GatewayError("beatapi call failed (429)"),
                    resp(("list_dir", {"path": "backend"})))
    with pytest.raises(agent_loop.StopRun) as e:
        agent_loop.run_agent(TASK, box(tree), chat, gateway_error=GatewayError, save=saved.append)
    assert "429" in str(e.value) and chat.calls == 2  # the third scripted reply is never requested
    assert saved[-1]["error"].startswith("GatewayError") and saved[-1]["requests"] == 1


def test_global_live_cap_stops(tree):
    chat = FakeChat(*[resp(("list_dir", {"path": "backend"})) for _ in range(5)])
    counter = agent_loop.LiveCounter(cap=2)
    with pytest.raises(agent_loop.StopRun):
        agent_loop.run_agent(TASK, box(tree), chat, counter=counter)
    assert chat.calls == 2 and counter.live == 2


def test_cache_hits_do_not_count_as_live(tree):
    chat = FakeChat(resp(("list_dir", {"path": "backend"}), cache_hit=True),
                    resp(("submit_final", {"diagnosis": "d", "root_cause_file": "f", "summary": "s"}),
                         cache_hit=True))
    counter = agent_loop.LiveCounter(cap=2)
    rec = agent_loop.run_agent(TASK, box(tree), chat, counter=counter)
    assert counter.live == 0 and rec["live_requests"] == 0 and rec["requests"] == 2


# --- usage guard --------------------------------------------------------------------------
GOOD = {"data": {"credit_balance": 0, "credits_settled": 0, "total_tasks": 3,
                 "by_model": [{"model": "glm-5.3-flash-free", "tasks": 3, "credits_settled": 0}]}}


def test_usage_guard_accepts_free_only(tmp_path):
    g = usage_guard.UsageGuard(lambda: GOOD, tmp_path / "s.json")
    assert g.check("x")["credit_balance"] == 0
    assert json.loads((tmp_path / "s.json").read_text())[0]["label"] == "x"


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(credits_settled=3),
    lambda d: d.update(credit_balance=5),
    lambda d: d["by_model"].append({"model": "glm-5.3-flash", "tasks": 1, "credits_settled": 0}),
    lambda d: d["by_model"][0].update(credits_settled=1),
])
def test_usage_guard_aborts_on_paid_usage_or_other_model(mutate, tmp_path):
    bad = json.loads(json.dumps(GOOD))
    mutate(bad["data"])
    with pytest.raises(usage_guard.UsageAnomaly):
        usage_guard.UsageGuard(lambda: bad, tmp_path / "s.json").check("t")


def test_usage_guard_aborts_when_endpoint_unreadable():
    def boom():
        raise OSError("down")

    with pytest.raises(usage_guard.UsageAnomaly):
        usage_guard.UsageGuard(boom).check("t")


def test_usage_anomaly_mid_task_propagates(tree):
    bad = json.loads(json.dumps(GOOD))
    bad["data"]["credits_settled"] = 1
    g = usage_guard.UsageGuard(lambda: bad)
    chat = FakeChat(*[resp(("list_dir", {"path": "backend"})) for _ in range(6)])
    counter = agent_loop.LiveCounter(cap=60, start=4)  # the 5th live request triggers the check
    with pytest.raises(usage_guard.UsageAnomaly):
        agent_loop.run_agent(TASK, box(tree), chat, guard=g, counter=counter)
    assert chat.calls == 1


# --- model guard (no network: refused before any request) ----------------------------------
def test_other_model_id_is_refused_before_network():
    from traceforge.agent import gateway
    from traceforge.config import Settings

    s = Settings(_env_file=None, llm_provider="beatapi", llm_model="glm-5.3-flash")
    with pytest.raises(GatewayError, match="only the exact model id"):
        gateway.chat([{"role": "user", "content": "hi"}], settings=s, client=SimpleNamespace())


# --- worktrees ----------------------------------------------------------------------------
@pytest.mark.parametrize("tid", ["T1", "T2", "T3", "T4"])
def test_buggy_worktree_is_stripped_and_cleaned_up(tid):
    import run_eval

    task = run_eval.load_task(tid)
    tree, hidden = worktree.build_visible(task, f"unit_{tid}", buggy=True)
    try:
        assert not (tree / ".git").exists()
        assert sorted(p.name for p in tree.iterdir()) == ["backend"]
        assert not (tree / "backend" / "tests" / "test_zz_hidden.py").exists()
        assert hidden  # scorer files exist, outside the tree
        for h in task["hidden"]:  # removed from the visible file, kept for the scorer
            vis = (tree / h["file"]).read_text(encoding="utf-8")
            assert all(n not in vis for n in h["names"])
        for rel, content in hidden.items():
            assert not (tree / rel).exists()
        assert any("unit_" in w for w in worktree.list_worktrees())
    finally:
        worktree.cleanup(tree)
    assert not tree.exists() and not any("unit_" in w for w in worktree.list_worktrees())


def test_cleanup_is_idempotent_and_prunes():
    p = worktree.create("unit_cleanup")
    worktree.cleanup(p)
    worktree.cleanup(p)
    assert not p.exists() and not worktree.list_worktrees()


# --- scoring ------------------------------------------------------------------------------
def test_self_correction_needs_edit_between_failure_and_pass():
    runs = [{"failed": 2, "edits_before": 0, "error": None}, {"failed": 0, "edits_before": 1, "error": None}]
    assert scoring.self_correction(runs)["detected"]
    runs[1]["edits_before"] = 0
    assert not scoring.self_correction(runs)["detected"]


def test_explanation_alone_is_never_repair_success():
    task = {"id": "TX", "hidden": [{"file": "f", "names": ["test_h"]}], "package_tests": ["tests"]}
    assert scoring.hidden_names(task) == ["test_h"]
    rc = scoring.root_cause({"gold": {"files": ["backend/a/b.py"], "functions": ["fn"],
                                      "mechanism": [["boom"]]}},
                            {"diagnosis": "b.py fn boom", "root_cause_file": "backend/a/b.py", "summary": "s"})
    assert rc["auto_correct"] and rc["needs_human_review"]
