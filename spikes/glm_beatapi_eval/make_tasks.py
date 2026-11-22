"""Writes tasks/T1..T4.json (bug report shown to the model + hidden ground truth). Run once."""

import json
from pathlib import Path

OUT = Path(__file__).parent / "tasks"
B = "backend/traceforge/"

T1_OLD = '''def _limitation(cause: str | None, verified: bool) -> str:
    """Only claim 'verified' when the incident really reached VERIFIED."""
    if cause in ("configuration", "application_code") and not verified:
        return _UNVERIFIED
    return LIMITATIONS.get(cause or "", DEFAULT_LIMITATION)
'''
T1_NEW = '''def _limitation(cause: str | None) -> str:
    return LIMITATIONS.get(cause or "", DEFAULT_LIMITATION)
'''
T1_CALL_OLD = "        limitations=_limitation(cause, any(e.to_state is State.VERIFIED for e in events)),\n"
T1_CALL_NEW = "        limitations=_limitation(cause),\n"

TRUNC_CLASS = '''class OutputTruncated(GatewayError):
    """The reply hit the output-token cap (finish_reason 'length') and has no usable content.
    Reasoning models can spend the whole budget on hidden reasoning; raise llm_max_output_tokens."""


'''

T4_HIDDEN = '''"""Scorer-only check: a provider choice without finish_reason must not crash chat()."""
from types import SimpleNamespace

from traceforge.agent.gateway import chat
from traceforge.config import Settings


class _Client:
    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        msg = SimpleNamespace(content="hello", tool_calls=None)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=msg)],  # no finish_reason attribute at all
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
        )


def test_choice_without_finish_reason(tmp_path):
    s = Settings(_env_file=None, llm_cache_dir=tmp_path / "c", llm_call_log=tmp_path / "l.jsonl",
                 llm_max_rps=1000)
    r = chat([{"role": "user", "content": "hi"}], settings=s, client=_Client())
    assert r.content == "hello" and r.finish_reason is None
'''

TASKS = {
    "T1": {
        "title": "Report claims verification that never happened",
        "kind": "repair",
        "bug_report": (
            "Incident report (from an end-to-end run of the pipeline on a real incident).\n\n"
            "An incident whose cause class was `configuration` was diagnosed, a patch was "
            "proposed, but no patch ever passed the hidden test suite, so the incident never "
            "reached the VERIFIED state. When I fetched `GET /incidents/{id}/report`, the "
            "`limitations` field said: \"Verified only by the lab test suites on a snapshot. Not "
            "deployed. Review the diff.\" That is wrong for this incident: the report states a "
            "verification that never took place, and a reviewer could trust an unconfirmed "
            "hypothesis. A properly verified incident should still carry that caveat.\n\n"
            "Observed by reading the JSON returned by the report endpoint after the run."
        ),
        "gold": {
            "files": [B + "reports/builder.py"],
            "functions": ["_limitation"],
            "mechanism": [
                [r"\bverified\b|VERIFIED"],
                [r"not\b.{0,40}verified|never reach|unverified|without verif|did not reach"
                 r"|regardless|whether"],
            ],
        },
        "injections": [
            {"file": B + "reports/builder.py", "old": T1_OLD, "new": T1_NEW},
            {"file": B + "reports/builder.py", "old": T1_CALL_OLD, "new": T1_CALL_NEW},
        ],
        "hidden": [{"file": "backend/tests/reports/test_report.py", "names": [
            "test_unverified_repairable_incident_is_not_labelled_verified",
            "test_verified_incident_keeps_the_verified_caveat"]}],
        "package_tests": ["tests/reports"],
        "ask": "diagnose and fix",
    },
    "T2": {
        "title": "Never-diagnosed incident reported as SUPPORTED",
        "kind": "repair",
        "bug_report": (
            "Found during a live UI walkthrough. I created a brand-new incident (symptom "
            "\"boom\", service shop_api) and did not run any diagnosis on it, so it sits in state "
            "CREATED with no cause class and no diagnosis data. `GET /incidents/{id}/report` "
            "nevertheless returns `root_cause.status` = \"SUPPORTED\", and the UI shows a green "
            "'supported' root cause for an incident nobody has analysed. Expected: the report "
            "must not present an undiagnosed incident as having a supported root cause.\n\n"
            "Observed in the JSON of the report endpoint and in the UI badge."
        ),
        "gold": {
            "files": [B + "reports/builder.py", B + "reports/schemas.py"],
            "functions": ["build_report"],
            "mechanism": [
                [r"NOT_DIAGNOSED|not.diagnosed|undiagnosed|never diagnosed"],
                [r"SUPPORTED"],
                [r"status"],
            ],
        },
        "injections": [
            {"file": B + "reports/builder.py",
             "old": '    status = "SUPPORTED" if (cause or diag) else "NOT_DIAGNOSED"\n',
             "new": '    status = "SUPPORTED"\n'},
            {"file": B + "reports/schemas.py",
             "old": 'RootCauseStatus = Literal["SUPPORTED", "INCONCLUSIVE", "RUNTIME_DEPENDENCY", '
                    '"NOT_DIAGNOSED"]\n',
             "new": 'RootCauseStatus = Literal["SUPPORTED", "INCONCLUSIVE", "RUNTIME_DEPENDENCY"]\n'},
        ],
        "hidden": [{"file": "backend/tests/reports/test_report.py", "names": [
            "test_incident_without_diagnosis_is_not_reported_as_supported"]}],
        "package_tests": ["tests/reports"],
        "ask": "diagnose and fix",
    },
    "T3": {
        "title": "Truncated patch reply reported as no_edit",
        "kind": "repair",
        "bug_report": (
            "Seen when running the pipeline with a reasoning model (one that spends many tokens "
            "on hidden reasoning before answering). The patch stage fails and the pipeline "
            "records the failure reason `no_edit`, which suggests the model produced no usable "
            "SEARCH/REPLACE block. Looking at the provider response and the call log: the patch "
            "request actually returned an EMPTY reply with finish_reason 'length', and the call "
            "log shows tokens_out equal to the output cap (1024). So the real cause was that the "
            "reply was cut off at the output-token cap, but nothing in the pipeline says so; "
            "operators wasted time prompt-engineering. Expected: a clear truncation reason "
            "instead of `no_edit`, and the output-token cap should not be a hard-coded value.\n\n"
            "Observed in the call log (runs/llm_calls.jsonl) and the stored failure reason."
        ),
        "gold": {
            "files": [B + "agent/gateway.py", B + "agent/patch.py", B + "config.py"],
            "functions": ["ask_patch", "request_patch", "chat"],
            "mechanism": [
                [r"finish_reason|length|truncat"],
                [r"max_tokens|1024|output.token|llm_max"],
                [r"no_edit"],
            ],
        },
        "injections": [
            {"file": B + "agent/gateway.py", "old": TRUNC_CLASS, "new": ""},
            {"file": B + "agent/gateway.py",
             "old": '"max_tokens": max_tokens or s.llm_max_output_tokens,',
             "new": '"max_tokens": max_tokens or 1024,'},
            {"file": B + "agent/patch.py",
             "old": "from traceforge.agent.gateway import GatewayError, OutputTruncated\n",
             "new": "from traceforge.agent.gateway import GatewayError\n"},
            {"file": B + "agent/patch.py",
             "old": '    if resp.finish_reason == "length" and not (resp.content or "").strip():\n'
                    '        raise OutputTruncated("patch reply truncated at the output-token '
                    'cap with no content")\n',
             "new": ""},
            {"file": B + "agent/patch.py",
             "old": '    except OutputTruncated:\n        return None, None, "output_truncated"\n',
             "new": ""},
            {"file": B + "config.py",
             "old": "    llm_max_output_tokens: int = 4096  # reasoning models spend part of this "
                    "on hidden reasoning\n",
             "new": ""},
        ],
        "hidden": [{"file": "backend/tests/agent/test_pipeline.py", "names": [
            "test_empty_truncated_patch_reply_is_reported_as_output_truncated"]}],
        "package_tests": ["tests/agent"],
        "ask": "diagnose and fix",
    },
    "T4": {
        "title": "Gateway crashes when a provider omits finish_reason (+ write regression test)",
        "kind": "repair_and_test",
        "bug_report": (
            "Some OpenAI-compatible providers omit `finish_reason` from a response choice. When "
            "that happens, `traceforge.agent.gateway.chat(...)` crashes while building its "
            "`ModelResponse` with `AttributeError: ... object has no attribute 'finish_reason'`, "
            "instead of returning a response (the reply content and tool calls were perfectly "
            "fine). Observed via a provider whose JSON choice has only `index` and `message`; "
            "several tests in the existing gateway test file also fail with the same "
            "AttributeError.\n\n"
            "Additional deliverable for this task: besides finding the root cause and fixing it, "
            "write your OWN regression test in a NEW file "
            "`backend/tests/agent/test_finish_reason_regression.py`. It must fail on the buggy "
            "code and pass once the bug is fixed."
        ),
        "gold": {
            "files": [B + "agent/gateway.py"],
            "functions": ["chat"],
            "mechanism": [
                [r"finish_reason"],
                [r"AttributeError|getattr|missing|omit|lacks|absent|no attribute"],
            ],
        },
        "injections": [
            {"file": B + "agent/gateway.py",
             "old": '        finish_reason=getattr(raw.choices[0], "finish_reason", None),\n',
             "new": "        finish_reason=raw.choices[0].finish_reason,\n"},
        ],
        "hidden": [],
        "hidden_extra_files": {"backend/tests/agent/test_zz_hidden.py": T4_HIDDEN},
        "hidden_ids": ["test_choice_without_finish_reason"],
        "package_tests": ["tests/agent"],
        "required_test_file": "backend/tests/agent/test_finish_reason_regression.py",
        "ask": "diagnose, fix, and write a regression test",
    },
}

for tid, t in TASKS.items():
    t["id"] = tid
    (OUT / f"{tid}.json").write_text(json.dumps(t, indent=1), encoding="utf-8")
print("wrote", list(TASKS))
