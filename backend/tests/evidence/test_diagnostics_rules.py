# ruff: noqa: E501
"""Deterministic diagnostics (traceforge.diagnostics): hand-written evidence in the shape the
collector produces. Offline, no model. Rules must fire on their pattern and stay quiet otherwise."""

import hashlib

from traceforge.agent import symptom
from traceforge.contracts.evidence import EvidenceBundle, EvidenceItem
from traceforge.contracts.test_run import TestOutcome, TestRunResult
from traceforge.diagnostics import findings_as_items, is_finding, run_rules


def mk(i: int, kind: str, content: str, service: str = "shop_api", **kw) -> EvidenceItem:
    return EvidenceItem(
        id=f"EV-{i:04d}",
        kind=kind,  # type: ignore[arg-type]
        service=service,
        content=content,
        sha256=hashlib.sha256(content.encode()).hexdigest(),
        **kw,
    )


def bundle(*items: EvidenceItem) -> EvidenceBundle:
    return EvidenceBundle(incident_id="i", base_sha="x", compose_sha256="0" * 64, items=list(items))


def rules(ev: EvidenceBundle) -> dict[str, str]:
    return {f.rule: f.render() for f in run_rules(ev)}


def decl(i, name, typ, val, path="lab/shop_api/app/settings.py", service="shop_api"):
    body = f"settings.{name} [{typ}]" + (f" = {val}" if val is not None else "")
    return mk(i, "config", body, service, path=path, line=10 + i)


def run(out, failed_ids, passed=0):
    return TestRunResult(
        passed=passed,
        failed=len(failed_ids),
        tests=[TestOutcome(id=t, outcome="failed") for t in failed_ids],
        stdout_tail=out,
        duration_ms=1,
        timed_out=False,
    )


COMPOSE = [
    mk(
        20,
        "compose",
        "service lab_redis\nimage: redis:7\ndepends_on: []\nenvironment: \n",
        "lab_redis",
    ),
    mk(
        21,
        "compose",
        "service worker\nimage: w\ndepends_on: ['lab_redis']\nenvironment: REDIS_HOST=lab_redis, ORDER_QUEUE=q\n",
        "worker",
    ),
    mk(22, "compose", "service shop_api\nimage: s\ndepends_on: []\nenvironment: DB_HOST=lab_db\n"),
]
GAI = "socket.gaierror: [Errno -2] Name or service not known\nredis.exceptions.ConnectionError: Error -2 connecting to {h}:6379. Name or service not known."


def test_unresolved_host_not_in_compose_points_at_the_declaring_default_without_a_verdict():
    ev = bundle(
        mk(1, "log", GAI.format(h="redis-broker.internal")),
        decl(2, "redis_host", "str", "'redis-broker.internal'"),
        decl(3, "redis_port", "int", "6379"),
        *COMPOSE,
    )
    f = rules(ev)["hostname_unresolved"]
    assert "'redis-broker.internal'" in f and "not a compose service" in f
    assert "EV-0002" in f and "EV-0021" in f  # the declaring default and the compose service
    assert "does not set it" in f
    assert "fix" not in f.lower() and "should be" not in f.lower()


def test_host_that_is_a_compose_service_with_a_dead_container_is_a_dependency_issue():
    ev = bundle(
        mk(
            1,
            "health",
            "container t-lab_redis-1: exited (health: unhealthy), restart_count=0, exit_code=0",
            "lab_redis",
        ),
        mk(2, "log", GAI.format(h="lab_redis")),
        *COMPOSE,
    )
    r = rules(ev)
    assert "container_down" in r and "lab_redis" in r["container_down"]
    assert "not a compose service" not in r.get("hostname_unresolved", "")
    assert "EV-0001" in r["hostname_unresolved"]


def test_healthy_running_containers_are_not_findings():
    ev = bundle(
        mk(
            1,
            "health",
            "container t-lab_db-1: running (health: healthy), restart_count=0",
            "lab_db",
        ),
        mk(2, "health", "container t-worker-1: running (health: none), restart_count=0", "worker"),
    )
    assert "container_down" not in rules(ev)


def test_crash_looping_container_is_reported():
    ev = bundle(
        mk(
            1,
            "health",
            "container t-worker-1: running (health: healthy), restart_count=5",
            "worker",
        )
    )
    assert "container_down" in rules(ev)


def test_startup_validation_names_the_fields():
    log = (
        "pydantic_core._pydantic_core.ValidationError: 2 validation errors for Settings\n"
        "db_user\n  Field required [type=missing, input_value={}, input_type=dict]\n"
        "redis_port\n  Input should be a valid integer [type=int_parsing]\n"
    )
    f = rules(bundle(mk(1, "log", log)))["startup_validation"]
    assert "db_user" in f and "redis_port" in f and "Settings" in f


def test_import_error_gets_file_and_line():
    log = (
        "Traceback (most recent call last):\n"
        '  File "/app/app/main.py", line 3, in <module>\n    from app import missing\n'
        "ImportError: cannot import name 'missing' from 'app'\n"
    )
    f = rules(bundle(mk(1, "log", log)))["code_error_location"]
    assert "ImportError" in f and "/app/app/main.py:3" in f


def test_site_packages_frames_are_not_blamed_for_a_syntax_error():
    log = (
        '  File "/opt/venv/lib/python3.12/site-packages/x.py", line 9, in f\n'
        "  File \"/app/app/orders.py\", line 12\n    x = (\nSyntaxError: '(' was never closed\n"
    )
    assert "/app/app/orders.py:12" in rules(bundle(mk(1, "log", log)))["code_error_location"]


FAIL_SYMPTOM = (
    "F\n=== FAILURES ===\n___ test_job_1 ___\n"
    "/reproducer/test_symptom.py:7: in test_job_1\n"
    "    assert observe_job(12, 1) == [True, 2, [1.0], 0, 0]\n"
    "E   AssertionError: assert [True, 2, [{left}], 0, 0] == [True, 2, [1.0], 0, 0]\n"
)


def with_failing(base_items, left):
    ev = bundle(*base_items)
    sym = symptom.build_symptom(
        {
            "reproducer": run(FAIL_SYMPTOM.format(left=left), ["test_symptom.py::test_job_1"]),
            "visible": run("", [], passed=14),
        }
    )
    return symptom.with_symptom(ev, sym)


WORKER = "lab/worker/settings.py"


def test_negated_value_and_negative_default_are_tied_together():
    ev = with_failing([decl(1, "backoff_base_s", "float", "-1.0", WORKER, "worker")], "-1.0")
    f = rules(ev)["symptom_sign"]
    assert "negation" in f and "backoff_base_s=-1.0" in f


def test_produced_value_that_is_a_power_of_ten_off_and_equals_a_default():
    ev = with_failing(
        [
            decl(1, "backoff_base_s", "float", "1000.0", WORKER, "worker"),
            decl(2, "max_retries", "int", "3", WORKER, "worker"),
        ],
        "1000.0",
    )
    f = rules(ev)["symptom_value_is_default"]
    assert "backoff_base_s=1000.0" in f and "max_retries" not in f


def test_default_equal_to_produced_value_is_ignored_without_a_power_of_ten_relation():
    ev = with_failing([decl(1, "tax_rate", "Decimal", "Decimal('0.17')")], "0.17")
    assert "symptom_value_is_default" not in rules(ev)


def test_implausible_defaults_only_under_a_failing_signal():
    items = [
        decl(1, "tax_rate", "Decimal", "Decimal('1.17')"),
        decl(2, "max_discount_pct", "int", "100"),
        decl(3, "backoff_base_s", "float", "0.0", WORKER, "worker"),
        decl(4, "free_shipping_over", "Decimal", "Decimal('50.00')"),
        decl(5, "shipping_fee", "Decimal", "Decimal('499')"),
    ]
    assert run_rules(bundle(*items)) == []  # nothing failed: no settings commentary
    texts = " ".join(f.text for f in run_rules(with_failing(items, "5.0")))
    for needle in (
        "tax_rate defaults to Decimal('1.17')",
        "max_discount_pct",
        "backoff_base_s",
        "shipping_fee",
    ):
        assert needle in texts


def test_plausible_defaults_stay_quiet_even_when_something_failed():
    items = [
        decl(1, "tax_rate", "Decimal", "Decimal('0.17')"),
        decl(2, "max_discount_pct", "int", "30"),
        decl(3, "shipping_fee", "Decimal", "Decimal('4.99')"),
        decl(4, "low_stock_level", "int", "3"),
        decl(5, "backoff_base_s", "float", "1.0", WORKER, "worker"),
    ]
    assert "implausible_default" not in rules(with_failing(items, "5.0"))


def test_queue_name_that_differs_between_services_is_flagged_and_env_wins():
    ev = bundle(
        decl(1, "order_queue", "str", "'orders:confirm'"),
        decl(2, "order_queue", "str", "'orders:confrim'", WORKER, "worker"),
        mk(3, "config", "ORDER_QUEUE=orders:confirm", "shop_api"),
    )
    f = rules(ev)["name_mismatch"]
    assert "orders:confrim" in f and "orders:confirm" in f and "EV-0002" in f
    same = bundle(
        decl(1, "order_queue", "str", "'orders:confirm'"),
        decl(2, "order_queue", "str", "'orders:confirm'", WORKER, "worker"),
    )
    assert "name_mismatch" not in rules(same)


def test_nothing_observed_hint_needs_a_passing_test_run_and_a_clean_runtime():
    health = mk(1, "health", "container t-shop_api-1: running (health: healthy), restart_count=0")
    log = mk(2, "log", "INFO: Uvicorn running\nINFO: GET /health/live 200 OK")
    quiet = {
        "reproducer": run("", [], passed=1),
        "visible": run("", [], passed=30),
    }
    ev = symptom.with_symptom(bundle(health, log), symptom.build_symptom(quiet))
    f = rules(ev)["nothing_observed"]
    assert "abstaining" in f
    # no test run at all: no claim
    assert "nothing_observed" not in rules(bundle(health, log))
    # an error in the logs: no hint
    bad = mk(2, "log", "ERROR boom\nTraceback (most recent call last):")
    assert "nothing_observed" not in rules(
        symptom.with_symptom(bundle(health, bad), symptom.build_symptom(quiet))
    )
    # a dead dependency: no hint
    dead = mk(
        3, "health", "container t-lab_redis-1: exited (health: unhealthy), exit_code=1", "lab_redis"
    )
    assert "nothing_observed" not in rules(
        symptom.with_symptom(bundle(health, log, dead), symptom.build_symptom(quiet))
    )


def test_findings_are_issue_items_with_continuing_ids_and_no_gold_language():
    ev = with_failing([decl(1, "backoff_base_s", "float", "-1.0", WORKER, "worker")], "-1.0")
    ids = [i.id for i in ev.items]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    fi = [i for i in ev.items if is_finding(i)]
    assert fi and all(i.kind == "issue" and i.content.startswith("FINDING") for i in fi)
    text = " ".join(i.content.lower() for i in fi)
    for banned in ("gold", "expected answer", "hidden", "mutation", "root cause is"):
        assert banned not in text
    # evidence ids cited by a finding exist in the bundle
    import re

    for i in fi:
        for eid in re.findall(r"EV-\d{4}", i.content):
            assert eid in ids


def test_findings_never_change_existing_ids_and_a_broken_rule_does_not_raise():
    base = bundle(mk(1, "log", "x"))
    assert findings_as_items(base, []) == []
    weird = bundle(mk(1, "config", "settings.x [int] = Decimal('", path="a.py", line=1))
    assert run_rules(weird) == []


def test_no_findings_means_with_symptom_is_unchanged():
    ev = bundle(mk(1, "health", "container t-shop_api-1: running (health: healthy)"))
    sym = symptom.build_symptom({"visible": run("", ["t.py::test_a"], passed=1)})
    out = symptom.with_symptom(ev, sym, findings=False)
    assert not any(is_finding(i) for i in out.items)


def test_queue_name_of_the_target_service_is_compared_with_other_services_compose_env():
    ev = bundle(
        decl(1, "order_queue", "str", "'orders:confrim'", WORKER, "worker"),
        mk(2, "compose", "service shop_api\nimage: s\nenvironment: ORDER_QUEUE=orders:confirm\n"),
        mk(3, "compose", "service worker\nimage: w\nenvironment: DB_HOST=lab_db\n", "worker"),
    )
    f = rules(ev)["name_mismatch"]
    assert "orders:confrim" in f and "orders:confirm" in f and "compose environment" in f
