"""dev-d1 isolation: the runner refuses to mix pipeline v5 with the test split or formal results."""

import pytest

from traceforge.evaluation import real_run, runner


def argv(tmp_path, *extra, out="development"):
    return [
        "--manifest", "m.json", "--condition", "L0", "--run-id", "dev-x",
        "--out", str(tmp_path / out), *extra,
    ]  # fmt: skip


@pytest.mark.parametrize(
    "extra,out",
    [
        (["--pipeline", "v5", "--split", "test"], "development"),  # frozen test split
        (["--pipeline", "v5", "--split", "dev"], "official"),  # formal results directory
        (["--diagnose-only"], "development"),  # diagnose-only without v5
    ],
)
def test_runner_refuses_unsafe_dev_d1_combinations(tmp_path, extra, out):
    assert runner.main(argv(tmp_path, *extra, out=out)) == 2


def test_v5_components_record_dev_d1_and_v4_records_nothing():
    comp = real_run.components("v5")
    assert comp["config_id"] == "dev-d1" and "disabled" in comp["cache"]
    assert real_run.components("v4") == {}


def test_a_live_only_request_neither_reads_nor_writes_the_cache(tmp_path):
    from types import SimpleNamespace

    from pydantic import SecretStr

    from traceforge.agent import gateway
    from traceforge.config import Settings

    class Client:
        calls = 0

        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kw):
            Client.calls += 1
            msg = SimpleNamespace(content="hi", tool_calls=[])
            return SimpleNamespace(
                choices=[SimpleNamespace(message=msg, finish_reason="stop")],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )

    s = Settings(
        _env_file=None, llm_cache_dir=tmp_path / "c", llm_call_log=tmp_path / "l.jsonl",
        llm_max_rps=1000, openrouter_api_key=SecretStr("k"),
    )  # fmt: skip
    msgs = [{"role": "user", "content": "x"}]
    a = gateway.chat(msgs, settings=s, client=Client(), use_cache=False)
    b = gateway.chat(msgs, settings=s, client=Client(), use_cache=False)
    assert (a.cache_hit, b.cache_hit, Client.calls) == (False, False, 2)
    assert not (tmp_path / "c").exists()


# --- provider/model/pipeline can never change inside one evaluation run -----------------------

import json  # noqa: E402

from test_eval_runner import QUIET, SAMPLES, fake  # noqa: E402

from traceforge.evaluation.runner import run_experiment  # noqa: E402


@pytest.fixture
def manifest(tmp_path):
    cases = []
    for i, split in enumerate(["dev", "dev", "test"]):
        c = json.loads((SAMPLES / "case_manifest.code.json").read_text("utf-8"))
        c.update(case_id=f"case-{i}", split=split)
        cases.append(c)
    p = tmp_path / "data" / "manifest.json"
    p.parent.mkdir()
    p.write_text(json.dumps(cases), "utf-8")
    return p


def _run(manifest, tmp_path, **kw):
    return run_experiment(
        manifest, "L0", "dev-x", fake(), tmp_path / "development", 1, "dev", **QUIET, **kw
    )


def test_v5_run_meta_is_development_with_the_dev_d1_prompt_hash(manifest, tmp_path):
    from traceforge.agent import prompting

    out = _run(manifest, tmp_path, pipeline="v5", diagnose_only=True)
    meta = json.loads((out / "meta.json").read_text("utf-8"))
    assert meta["tier"] == "development" and meta["pipeline_version"] == "v5"
    assert meta["dev_config"] == "dev-d1" and meta["diagnose_only"] is True
    assert meta["prompt_hash"] == prompting.prompt_hash("v5")


def test_formal_axforge_run_meta_is_unchanged(manifest, tmp_path):
    out = run_experiment(manifest, "L0", "off-x", fake(), tmp_path / "o", 1, "dev", **QUIET)
    meta = json.loads((out / "meta.json").read_text("utf-8"))
    assert meta["tier"] == "official" and meta["pipeline_version"] == "v4"
    assert meta["dev_config"] is None


@pytest.mark.parametrize(
    "kw",
    [
        {"provider": "beatapi", "model": "glm-5.3-flash-free", "pipeline": "v5"},  # provider swap
        {"provider": "axforge", "model": "other-model", "pipeline": "v5"},
        {"provider": "axforge", "model": "glm-5.3-flash", "pipeline": "v4"},  # pipeline swap
    ],
)
def test_resume_refuses_to_change_provider_model_or_pipeline(manifest, tmp_path, kw):
    base = dict(provider="axforge", model="glm-5.3-flash", pipeline="v5")
    _run(manifest, tmp_path, **base)
    with pytest.raises(ValueError, match="different provider/model/pipeline"):
        _run(manifest, tmp_path, **kw)
    assert _run(manifest, tmp_path, **base)  # the same binding resumes normally


def test_a_halted_run_resumes_with_the_same_binding_and_keeps_finished_cases(manifest, tmp_path):
    calls: list[str] = []
    base = dict(provider="axforge", model="glm-5.3-flash", pipeline="v5")
    run_experiment(
        manifest, "L0", "dev-x", fake(calls, fail_on="case-1"), tmp_path / "d", 1, "dev",
        **QUIET, **base,
    )  # fmt: skip
    again: list[str] = []
    run_experiment(manifest, "L0", "dev-x", fake(again), tmp_path / "d", 1, "dev", **QUIET, **base)
    assert calls == ["case-0", "case-1"] and again == ["case-1"]  # case-0 is not run again


def test_usage_report_separates_development_spend_from_official(tmp_path):
    from traceforge.evaluation import usage_report

    rows = [
        {"type": "authorization", "run_id": "official-axforge-L0-x"},
        {"type": "request", "input_tokens": 100, "output_tokens": 10},
        {"type": "authorization", "run_id": "dev-axforge-L0-dd1-l1"},
        {"type": "request", "input_tokens": 50, "output_tokens": 5},
        {"type": "error", "http_status": 429, "estimated_tokens": 7},
    ]
    p = tmp_path / "l.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    runs = usage_report.by_run(p)
    assert runs["dev-axforge-L0-dd1-l1"] == {"tokens": 62, "rows": 2, "tier": "development"}
    assert runs["official-axforge-L0-x"]["tokens"] == 110


def test_code_fingerprint_is_stable_and_changes_with_the_code(tmp_path):
    from traceforge.evaluation.fingerprint import FILES, PKG, code_fingerprint

    fp = code_fingerprint()
    assert fp == code_fingerprint() and set(fp["files"]) == set(FILES)  # every listed file exists
    (tmp_path / "a.py").write_bytes(b"x = 1\r\n")
    (tmp_path / "b.py").write_bytes(b"y = 2\n")
    one = code_fingerprint(("a.py", "b.py"), tmp_path)
    (tmp_path / "a.py").write_bytes(b"x = 1\n")  # CRLF vs LF only: same fingerprint
    assert code_fingerprint(("a.py", "b.py"), tmp_path) == one
    (tmp_path / "a.py").write_bytes(b"x = 2\n")
    assert code_fingerprint(("a.py", "b.py"), tmp_path)["sha256"] != one["sha256"]
    assert PKG.name == "traceforge"
