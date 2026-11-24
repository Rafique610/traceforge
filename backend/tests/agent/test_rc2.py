"""RC2 (P5-S10): each fix on fixed fixtures with fake gateways; RC1 untouched and the default."""

import json
from pathlib import Path

import pytest
from agentfakes import FakeChat, call, resp
from test_v5_diagnose import OVERLONG, tc
from v5helpers import bundle, item

from traceforge.agent.rc2 import config_check, rationale, repeat_guard, version
from traceforge.agent.rc2.version import (
    RC1_FINGERPRINT,
    VersionLabelError,
    rc2_fingerprint,
    run_label,
    select_chat_fn,
)
from traceforge.agent.tools import ToolError, dispatch, tool_schemas
from traceforge.evaluation import fingerprint as rc1fp
from traceforge.repair.edits import parse_blocks

PKG = Path(rc1fp.__file__).resolve().parents[1]


def blk(new, path="lab/shop_api/app/settings.py", old='REDIS_HOST = "x"'):
    return f"<<<<<<< SEARCH {path}\n{old}\n=======\n{new}\n>>>>>>> REPLACE"


EV = bundle(
    item(1, "compose", "service shop_api environment: REDIS_HOST=redis, PORT=8000"),
    item(2, "compose", "service redis image: redis:7"),
    item(3, "config", "settings.REDIS_HOST [str] = 'x'"),
)


def patch_resp(text):
    return resp(content=text)


# --- (a) rationale -------------------------------------------------------------------------


@pytest.mark.parametrize("cid", sorted(OVERLONG))
def test_overlong_rationale_is_truncated_logged_and_accepted(cid):
    log: list = []
    bad = type(call("x"))(name="submit_diagnosis", arguments=OVERLONG[cid])
    good_args = json.loads(OVERLONG[cid])
    assert len(good_args["rationale"]) > 500
    chat = FakeChat(resp(bad))
    out = select_chat_fn("rc2", chat, log)([{"role": "user", "content": "u"}], tool_schemas(True))
    # RC1 rejects the raw text with string_too_long; the truncated call no longer does.
    try:
        dispatch("submit_diagnosis", out.tool_calls[0].arguments, tc())
    except ToolError as e:
        assert "string_too_long" not in str(e)
    assert len(json.loads(out.tool_calls[0].arguments)["rationale"]) == 500
    assert log[0]["event"] == "rationale_truncated" and log[0]["original"] == good_args["rationale"]
    assert chat.n == 1  # no extra request


def test_truncate_rationale_unit():
    assert rationale.truncate_rationale('{"rationale": "short"}') == '{"rationale": "short"}'
    out = json.loads(rationale.truncate_rationale(json.dumps({"rationale": "a" * 900})))
    assert len(out["rationale"]) == 500
    assert rationale.truncate_rationale("not json") == "not json"


def test_rc1_still_rejects_the_same_overlong_rationale():
    with pytest.raises(ToolError):
        dispatch("submit_diagnosis", OVERLONG[sorted(OVERLONG)[0]], tc())


# --- (b) identical repeat ------------------------------------------------------------------


def test_identical_repeat_is_rejected_then_re_asked_with_visible_info_only():
    log: list = []
    first, second = (
        patch_resp(blk('REDIS_HOST = "lab_redis"')),
        patch_resp(blk('REDIS_HOST = "lab_redis"')),
    )
    third = patch_resp(blk('REDIS_HOST = "localhost"'))
    chat = FakeChat(first, second, third)
    g = select_chat_fn("rc2", chat, log, EV)
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    assert g(msgs, None).content == first.content
    out = g(msgs, None)  # identical: rejected, re-asked
    assert out.content == third.content
    assert chat.n == 3 and "DIFFERENT edit" in chat.messages[2][-1]["content"]
    assert "lab_redis" in chat.messages[2][-1]["content"]  # visible diagnostic note
    assert log[0]["event"] == "identical_edit_rejected"


def test_identical_after_re_ask_is_no_progress_empty_reply():
    log: list = []
    same = blk('REDIS_HOST = "lab_redis"')
    chat = FakeChat(patch_resp(same), patch_resp(same), patch_resp(same))
    g = select_chat_fn("rc2", chat, log, EV)
    m = [{"role": "user", "content": "u"}]
    g(m, None)
    assert g(m, None).content == ""
    assert log[-1]["reason"] == "no_progress_identical_edit"


def test_different_edits_and_diagnosis_calls_pass_through():
    chat = FakeChat(patch_resp(blk("A = 1")), patch_resp(blk("B = 2")), resp(call("read_evidence")))
    g = select_chat_fn("rc2", chat, [], EV)
    m = [{"role": "user", "content": "u"}]
    assert g(m, None).content.count("A = 1") == 1
    assert "B = 2" in g(m, None).content
    g(m, [{"function": {"name": "read_evidence"}}])
    assert chat.n == 3


def test_edit_key_ignores_non_edits():
    assert repeat_guard.edit_key("no blocks") is None


# --- (c) config-value diagnostic -----------------------------------------------------------


def test_unknown_host_value_is_flagged_known_ones_are_not():
    bad = check_flags('REDIS_HOST = "lab_redis"')
    assert len(bad) == 1 and "lab_redis" in bad[0]
    assert check_flags('REDIS_HOST = "localhost"') == []
    assert check_flags('REDIS_HOST = "redis"') == []  # a compose service
    assert check_flags("REDIS_PORT = 6379")  # unknown port flagged
    assert check_flags("PORT = 8000") == []  # compose-known
    assert check_flags("RETRIES = 3") == []  # not host/port-like


def check_flags(new):
    return config_check.check_edit_values(parse_blocks(blk(new, old="OLD = 1")), EV)


def test_unchanged_line_is_not_flagged():
    b = parse_blocks(blk('REDIS_HOST = "lab_redis"', old='REDIS_HOST = "lab_redis"'))
    assert config_check.check_edit_values(b, EV) == []


# --- RC1 unchanged / default / labels / fingerprint / no hidden content --------------------


def test_rc1_is_default_and_identity():
    chat = FakeChat()
    assert version.DEFAULT_VERSION == "rc1"
    assert select_chat_fn("rc1", chat) is chat
    with pytest.raises(VersionLabelError):
        select_chat_fn("rc3", chat)


def test_rc1_code_does_not_import_rc2():
    for rel in rc1fp.FILES:
        assert "rc2" not in (PKG / rel).read_text("utf-8"), rel


def test_rc1_fingerprint_is_frozen():
    assert rc1fp.code_fingerprint()["sha256"] == RC1_FINGERPRINT
    assert len(rc1fp.FILES) == 28


def test_rc2_fingerprint_differs_and_covers_rc1_plus_rc2_files():
    fp = rc2_fingerprint()
    assert fp["sha256"] != RC1_FINGERPRINT
    assert set(rc1fp.FILES) < set(fp["files"]) and "agent/rc2/rationale.py" in fp["files"]


def test_rc2_results_cannot_be_labelled_rc1():
    assert run_label("rc1", RC1_FINGERPRINT)["code_version"] == "rc1"
    with pytest.raises(VersionLabelError):
        run_label("rc2", RC1_FINGERPRINT)
    with pytest.raises(VersionLabelError):
        run_label("rc1", rc2_fingerprint()["sha256"])
    assert run_label("rc2", rc2_fingerprint()["sha256"])["code_version"] == "rc2"


def test_rc2_prompt_additions_contain_no_hidden_content():
    note = repeat_guard.NOTE.lower()
    for bad in ("hidden", "holdout", "gold", "reference patch"):
        assert bad not in note
    src = "".join(p.read_text("utf-8").lower() for p in (PKG / "agent/rc2").glob("*.py"))
    assert "hidden_result" not in src and "hidden_test" not in src
