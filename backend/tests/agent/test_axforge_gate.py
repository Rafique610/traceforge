"""AxForge billing hard gate: no request without explicit authorization; ceiling still applies.

Everything here uses fake clients and temporary ledgers: no network, no real ledger writes."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as N

import pytest

from traceforge.agent import axforge, gateway
from traceforge.agent.gateway import GatewayError, chat
from traceforge.config import Settings

BACKEND = Path(__file__).resolve().parents[2]


def ceiling_row(used: int) -> str:
    return json.dumps({"type": "request", "total_tokens": used}) + "\n"


@pytest.fixture(autouse=True)
def ledger(monkeypatch, tmp_path):
    path = tmp_path / "usage.jsonl"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(axforge, "LEDGER", path)
    monkeypatch.setattr(axforge, "_authorized_by", None)  # the default state of every process
    return path


class Client:
    def __init__(self):
        self.calls = 0
        self.chat = N(completions=N(create=self._create))

    def _create(self, **kw):
        self.calls += 1
        return N(
            choices=[N(message=N(content="OK", tool_calls=None), finish_reason="stop")],
            usage=N(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )


def settings():
    return Settings(llm_provider="axforge", llm_model="glm-5.3-flash", axforge_api_key="k")


def test_unauthorized_process_sends_nothing():
    c = Client()
    with pytest.raises(GatewayError, match="not authorized to call AxForge"):
        chat([{"role": "user", "content": "x"}], settings=settings(), client=c, use_cache=False)
    assert c.calls == 0 and not axforge.is_authorized()
    assert axforge.totals()["requests"] == 0  # nothing recorded either


def test_repeated_calls_and_retries_stay_refused():
    c = Client()
    for _ in range(5):  # a caller that retries gets nowhere
        with pytest.raises(GatewayError, match="AXFORGE REFUSED"):
            gateway._call_axforge(c, {"model": axforge.MODEL, "max_tokens": 100})
    assert c.calls == 0


def test_refusal_message_is_clear():
    msg = axforge.NOT_AUTHORIZED
    assert "dashboard" in msg and "auto top-up is OFF" in msg
    assert "--axforge-billing-verified" in msg and "No request was sent" in msg


def test_in_flight_reservation_is_not_taken_when_refused():
    with pytest.raises(axforge.AxForgeRefused):
        axforge.reserve(4096)
    assert axforge._inflight == 0


def test_authorized_process_can_call_and_usage_is_recorded(ledger):
    axforge.authorize("run-1")
    c = Client()
    chat([{"role": "user", "content": "x"}], settings=settings(), client=c, use_cache=False)
    assert c.calls == 1 and axforge.totals()["total_tokens"] == 15
    rows = [json.loads(x) for x in ledger.read_text("utf-8").splitlines()]
    assert rows[0]["type"] == "authorization" and rows[0]["run_id"] == "run-1"
    assert rows[0]["billing_verified_by_owner"] is True


def test_authorization_does_not_lift_the_token_ceiling(ledger):
    axforge.authorize("run-1")
    ledger.write_text(ceiling_row(axforge.SAFETY_CEILING - 50) + ledger.read_text("utf-8"), "utf-8")
    c = Client()
    with pytest.raises(GatewayError, match="safety ceiling"):
        gateway._call_axforge(c, {"model": axforge.MODEL, "max_tokens": 100})
    assert c.calls == 0 and axforge._inflight == 0


def test_authorization_does_not_lift_the_in_flight_reservation(ledger):
    axforge.authorize("run-1")
    ledger.write_text(
        ceiling_row(axforge.SAFETY_CEILING - 5000) + ledger.read_text("utf-8"), "utf-8"
    )
    axforge.reserve(4096)  # one request in flight uses most of the remainder
    with pytest.raises(axforge.AxForgeRefused, match="safety ceiling"):
        axforge.reserve(4096)  # a parallel worker's request would cross the ceiling
    axforge.release(4096)
    axforge.reserve(4096)
    axforge.release(4096)


def test_authorization_does_not_lift_a_recorded_stop():
    axforge.authorize("run-1")
    axforge.record_error(402)  # a billing signal appends a stop row
    with pytest.raises(GatewayError, match="stop was recorded"):
        gateway._call_axforge(Client(), {"model": axforge.MODEL, "max_tokens": 10})


def test_authorization_needs_a_readable_ledger_and_a_run_id(tmp_path, monkeypatch):
    monkeypatch.setattr(axforge, "LEDGER", tmp_path / "missing.jsonl")
    with pytest.raises(axforge.AxForgeRefused, match="missing"):
        axforge.authorize("run-1")
    assert not axforge.is_authorized()
    empty = tmp_path / "x.jsonl"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setattr(axforge, "LEDGER", empty)
    with pytest.raises(axforge.AxForgeRefused, match="name the run"):
        axforge.authorize("")


def test_revoke_closes_the_gate_again():
    axforge.authorize("run-1")
    axforge.revoke()
    with pytest.raises(axforge.AxForgeRefused):
        axforge.reserve(10)


def test_authorization_is_not_inherited_by_a_child_process():
    axforge.authorize("run-1")
    code = "from traceforge.agent import axforge; print(axforge.is_authorized())"
    r = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True, check=True
    )
    assert r.stdout.strip() == "False"  # workers and child processes start closed


def test_environment_variables_cannot_authorize(monkeypatch):
    for k in ("AXFORGE_BILLING_VERIFIED", "AXFORGE_AUTHORIZED", "TRACEFORGE_AXFORGE_OK"):
        monkeypatch.setenv(k, "1")
    with pytest.raises(axforge.AxForgeRefused):
        axforge.reserve(10)


# --- the runner -------------------------------------------------------------------------------
def runner_args(*extra):
    manifest = BACKEND.parent / "datasets" / "manifests" / "dev.json"
    return ["--manifest", str(manifest), "--condition", "L0", "--run-id", "t", *extra]


def test_runner_refuses_axforge_without_the_flag_including_by_default(monkeypatch, capsys):
    from traceforge.evaluation import runner

    ran = []
    monkeypatch.setattr(runner, "run_experiment", lambda *a, **k: ran.append(1))
    for extra in ([], ["--provider", "axforge"], ["--provider", "axforge", "--workers", "4"]):
        assert runner.main(runner_args(*extra)) == 4  # conditions default to axforge: refused
    assert ran == [] and "AXFORGE REFUSED" in capsys.readouterr().err
    assert not axforge.is_authorized()
    assert axforge.totals()["requests"] == 0


def test_runner_with_the_flag_authorizes_audits_and_warns(monkeypatch, capsys, ledger):
    from traceforge.evaluation import runner

    seen = {}
    monkeypatch.setattr(
        runner, "run_experiment", lambda *a, **k: seen.update(auth=axforge.is_authorized())
    )
    assert runner.main(runner_args("--axforge-billing-verified")) == 0
    out = capsys.readouterr().out
    assert seen["auth"] is True and "WARNING" in out and "3,000,000" in out
    assert json.loads(ledger.read_text("utf-8").splitlines()[0])["type"] == "authorization"


def test_beatapi_runs_do_not_need_or_use_the_axforge_flag(monkeypatch, tmp_path):
    from traceforge.agent import beatapi
    from traceforge.evaluation import runner

    monkeypatch.setattr(beatapi, "RUN_LOCK_FILE", tmp_path / "run.lock")
    monkeypatch.setattr(runner, "run_experiment", lambda *a, **k: None)
    rc = runner.main(runner_args("--provider", "beatapi", "--model", "glm-5.3-flash-free"))
    assert rc == 0 and not axforge.is_authorized()
    assert axforge.totals()["requests"] == 0  # ledgers stay separate


def test_authorization_rows_are_not_counted_as_usage():
    axforge.authorize("run-1")
    t = axforge.totals()
    assert t["requests"] == 0 and t["total_tokens"] == 0 and t["reliable"]


# --- strict budget tracking ---------------------------------------------------------------------
def test_reservation_includes_estimated_input_not_just_output(ledger):
    axforge.authorize("run-1")
    ledger.write_text(
        ceiling_row(axforge.SAFETY_CEILING - 5000) + ledger.read_text("utf-8"), "utf-8"
    )
    big = [{"role": "user", "content": "x" * 30_000}]  # about 10k input tokens
    c = Client()
    with pytest.raises(GatewayError, match="safety ceiling"):  # output alone (100) would have fit
        gateway._call_axforge(c, {"model": axforge.MODEL, "messages": big, "max_tokens": 100})
    assert c.calls == 0 and axforge._inflight == 0


def test_estimate_is_conservative():
    msgs = [{"role": "user", "content": "a" * 3000}]
    assert axforge.estimate_input_tokens({"messages": msgs}) >= 1000  # 3 chars per token or less


def test_failed_server_side_request_counts_its_estimated_input(ledger):
    axforge.authorize("run-1")

    class Boom(Client):
        def _create(self, **kw):
            e = RuntimeError("upstream")
            e.status_code = 503
            raise e

    c = Boom()
    msgs = [{"role": "user", "content": "x" * 3000}]
    with pytest.raises(GatewayError, match="503"):
        gateway._call_axforge(c, {"model": axforge.MODEL, "messages": msgs, "max_tokens": 100})
    t = axforge.totals()
    assert t["estimated_tokens"] >= 1000 and t["committed_tokens"] == t["estimated_tokens"]
    assert t["remaining_to_ceiling"] == axforge.SAFETY_CEILING - t["committed_tokens"]


def test_client_errors_that_cannot_have_cost_tokens_are_not_counted(ledger):
    axforge.authorize("run-1")

    class Limited(Client):
        def _create(self, **kw):
            e = RuntimeError("slow down")
            e.status_code = 429
            raise e

    with pytest.raises(GatewayError, match="429"):
        gateway._call_axforge(
            Limited(), {"model": axforge.MODEL, "messages": [], "max_tokens": 100}
        )
    assert axforge.totals()["estimated_tokens"] == 0


def test_truncating_or_resetting_the_ledger_is_detected(ledger):
    axforge.authorize("run-1")
    gateway._call_axforge(Client(), {"model": axforge.MODEL, "messages": [], "max_tokens": 100})
    assert axforge._read_floor(None) == 15
    ledger.write_text("", encoding="utf-8")  # someone empties the ledger
    c = Client()
    with pytest.raises(GatewayError, match="high-water mark"):
        gateway._call_axforge(c, {"model": axforge.MODEL, "messages": [], "max_tokens": 100})
    assert c.calls == 0


def test_floor_only_ever_rises(ledger):
    ledger.write_text(ceiling_row(500), "utf-8")
    assert axforge.raise_floor() == 500
    ledger.write_text(ceiling_row(100), "utf-8")
    assert axforge.raise_floor() == 500  # never lowered


def test_usage_report_shows_allowance_ceiling_reserve_and_stays_separate(ledger, tmp_path):
    from traceforge.evaluation.usage_report import report

    row = {
        "type": "request",
        "input_tokens": 54_703,
        "output_tokens": 12_274,
        "total_tokens": 66_977,
    }
    ledger.write_text(json.dumps(row) + "\n", "utf-8")
    r = report(ledger, tmp_path / "none.jsonl")
    ax = r["axforge"]
    assert (ax["provider_free_allowance"], ax["internal_ceiling"], ax["safety_reserve"]) == (
        3_000_000,
        3_000_000,
        0,
    )
    assert ax["committed_tokens"] == 66_977 and ax["remaining_to_ceiling"] == 2_933_023
    assert r["beatapi"]["requests"] == 0 and "tier" in r["beatapi"]


# --- the first provider failure halts AxForge too -----------------------------------------------
@pytest.mark.parametrize("status", [429, 500, 503, None])
def test_first_axforge_failure_stops_all_further_calls(ledger, status):
    axforge.authorize("run-1")

    class Failing(Client):
        def _create(self, **kw):
            self.calls += 1
            e = RuntimeError("boom")
            e.status_code = status
            raise e

    c = Failing()
    msgs = [{"role": "user", "content": "x"}]
    with pytest.raises(GatewayError):
        chat(msgs, settings=settings(), client=c, use_cache=False)
    for _ in range(4):  # the pipeline's own retries get no further network call
        with pytest.raises(GatewayError, match="halted after the first provider failure"):
            chat(msgs, settings=settings(), client=c, use_cache=False)
    assert c.calls == 1 and axforge.halted() is not None
    assert axforge._inflight == 0


def test_axforge_halt_does_not_affect_beatapi_state():
    from traceforge.agent import beatapi

    axforge.halt("503")
    assert beatapi.halted() is None


def test_runner_forces_one_worker_for_axforge(monkeypatch, capsys):
    from traceforge.evaluation import runner

    seen = {}
    monkeypatch.setattr(runner, "run_experiment", lambda *a, **k: seen.update(k))
    rc = runner.main(runner_args("--axforge-billing-verified", "--workers", "4"))
    assert rc == 0 and seen["workers"] == 1


# --- request spacing: see tests/agent/test_axforge_pacing.py -------------------------------------


def test_gate_is_released_after_a_failed_request(ledger):
    axforge.authorize("run-1")

    class Boom(Client):
        def _create(self, **kw):
            e = RuntimeError("x")
            e.status_code = 429
            raise e

    with pytest.raises(GatewayError):
        gateway._call_axforge(Boom(), {"model": axforge.MODEL, "messages": [], "max_tokens": 10})
    assert axforge._slot_file is None  # the shared request slot was freed
