"""Pipeline v5: symptom extraction, provenance, leakage screening and evidence representation.

Fixtures are real pytest output saved from earlier runs (the 010 reproducer from an F1 feedback
record, the 058 visible suite from a local run); nothing here calls a model.
"""

import hashlib
from pathlib import Path

import pytest
from v5helpers import bundle, item

from traceforge.agent import evidence_view, symptom
from traceforge.agent.real_sources import HiddenLeakGuard
from traceforge.contracts.test_run import TestOutcome, TestRunRequest, TestRunResult

FIX = Path(__file__).parent / "fixtures"
REPRO = (FIX / "pytest_reproducer_010.txt").read_text("utf-8")
VISIBLE = (FIX / "pytest_visible_058.txt").read_text("utf-8")


def result(text, ids, passed=0):
    return TestRunResult(
        passed=passed,
        failed=len(ids),
        tests=[TestOutcome(id=i, outcome="failed") for i in ids],
        stdout_tail=text,
        duration_ms=1,
        timed_out=False,
    )


REPRO_RUN = result(REPRO, ["test_symptom.py::test_price_1", "test_symptom.py::test_price_2"])
VIS_IDS = [
    "shop_api/tests/test_pricing_rules.py::test_quote_chains_the_rules_with_default_settings",
    "shop_api/tests/test_pricing_rules.py::test_quote_endpoint_and_unknown_coupon",
]
VISIBLE_RUN = result(VISIBLE, VIS_IDS, passed=33)


# --- extraction -------------------------------------------------------------------------------


def test_reproducer_symptom_keeps_endpoint_inputs_and_compared_values():
    items = symptom.parse_failures(REPRO_RUN, "reproducer")
    first = items[0]
    assert first.test_id == "test_symptom.py::test_price_1"
    assert first.request == ["GET /orders/1/quote?coupon=staff50"]  # endpoint + query input
    assert first.check.startswith("assert observe_price(") and '"staff50"' in first.check
    assert (first.left, first.right) == ("[200, '9.35']", "[200, '11.10']")  # got vs required
    assert first.location == "/reproducer/test_symptom.py:7"
    assert any("At index 1 diff" in d for d in first.detail)
    assert "GET /orders/1/quote?coupon=staff50" in first.text()


def test_visible_suite_failures_are_listed_with_normalised_paths():
    items = symptom.parse_failures(VISIBLE_RUN, "visible")
    assert [i.test_id for i in items] == VIS_IDS
    assert all("\\" not in (i.location or "") for i in items)


def test_windows_separators_in_pytest_output_are_normalised():
    out = REPRO.replace("/reproducer/test_symptom.py", "shop_api\\tests\\test_x.py")
    r = result(out, ["shop_api\\tests\\test_x.py::test_price_1"])
    it = symptom.parse_failures(r, "visible")[0]
    assert it.test_id.startswith("shop_api/tests/test_x.py::") and "\\" not in it.location


def test_symptom_is_bounded_and_marks_no_failure_and_sandbox_error():
    ok = result("1 passed", [], passed=1)
    assert symptom.build_symptom({"reproducer": ok}).status == "no_failure"
    bad = TestRunResult(
        passed=0, failed=0, tests=[], stdout_tail="", duration_ms=1, timed_out=False, error="boom"
    )
    assert symptom.build_symptom({"reproducer": bad}).status == "sandbox_error"
    sym = symptom.build_symptom({"reproducer": REPRO_RUN, "visible": VISIBLE_RUN})
    assert sum(len(t) for t in sym.texts()) < symptom.MAX_TOTAL_CHARS + 600


# --- provenance -------------------------------------------------------------------------------


def test_every_symptom_item_records_its_suite_and_the_hash_of_the_raw_output():
    sym = symptom.build_symptom({"reproducer": REPRO_RUN, "visible": VISIBLE_RUN})
    assert {i.suite for i in sym.items} == {"reproducer", "visible"}
    for i in sym.items:
        raw = REPRO if i.suite == "reproducer" else VISIBLE
        assert i.source_sha256 == hashlib.sha256(raw.encode()).hexdigest()
    assert set(sym.sources) == {"reproducer", "visible"} and sym.counts["visible"]["failed"] == 2


def test_symptom_evidence_items_are_appended_with_origin_and_location():
    base = bundle(item(1, "health", "ok"), item(2, "log", "started"))
    sym = symptom.build_symptom({"reproducer": REPRO_RUN})
    out = symptom.with_symptom(base, sym)
    assert [i.id for i in out.items[:2]] == ["EV-0001", "EV-0002"]  # existing ids unchanged
    new = out.items[2:]
    assert all(i.kind == "issue" and i.content.startswith("SYMPTOM") for i in new)
    assert all((i.scope, i.basis) == ("runtime", "observed") for i in new)
    assert all("visible test run on the base commit" in i.origin for i in new)
    located = [i for i in new if i.path]
    assert located and located[0].path == "/reproducer/test_symptom.py" and located[0].line == 7
    assert out.items[2].sha256 == hashlib.sha256(out.items[2].content.encode()).hexdigest()


def test_symptom_view_recovers_tests_and_requests_for_retrieval():
    sym = symptom.build_symptom({"reproducer": REPRO_RUN, "visible": VISIBLE_RUN})
    view = symptom.symptom_view(symptom.with_symptom(bundle(item(1, "health", "ok")), sym))
    assert ("visible", VIS_IDS[0]) in view.tests and (
        "reproducer",
        "test_symptom.py::test_price_1",
    ) in view.tests
    assert ("GET", "/orders/1/quote?coupon=staff50") in view.requests


# --- leakage screening ------------------------------------------------------------------------


def _guard(tmp_path):
    hidden = tmp_path / "hidden" / "c1"
    hidden.mkdir(parents=True)
    (hidden / "test_hidden_behaviour.py").write_text(
        "def test_price_1():\n    pass\n\ndef test_price_3():\n    pass\n"
    )
    vis = tmp_path / "repro"
    vis.mkdir()
    (vis / "test_symptom.py").write_text("def test_price_1():\n    pass\n")
    return HiddenLeakGuard(tmp_path / "hidden", ["c1"], [vis])


def test_clean_visible_symptom_passes_even_with_a_name_shared_with_hidden_tests(tmp_path):
    sym = symptom.build_symptom({"reproducer": REPRO_RUN})
    assert "test_price_1" in sym.texts()[1]
    assert symptom.validate(sym, _guard(tmp_path).check) == []


def test_hidden_only_name_or_file_or_path_blocks_the_symptom(tmp_path):
    guard = _guard(tmp_path)
    for leak in ("test_price_3", "test_hidden_behaviour.py", "datasets/hidden_tests/c1"):
        out = REPRO.replace("At index 1 diff", f"note {leak}")
        sym = symptom.build_symptom({"reproducer": result(out, ["test_symptom.py::test_price_1"])})
        assert any(r.startswith("hidden_marker") for r in symptom.validate(sym, guard.check)), leak


def test_secret_looking_text_blocks_the_symptom():
    out = REPRO.replace("At index 1 diff", "password=hunter2xx")
    sym = symptom.build_symptom({"reproducer": result(out, ["test_symptom.py::test_price_1"])})
    assert "secret_pattern" in symptom.validate(sym)


def test_collect_symptom_never_requests_the_hidden_suite():
    seen = []

    def run_tests(req: TestRunRequest):
        seen.append(req.suite)
        return REPRO_RUN if req.suite == "reproducer" else VISIBLE_RUN

    sym = symptom.collect_symptom(run_tests, "/wt", "c1")
    assert seen == ["reproducer", "visible"] and "hidden" not in seen and sym.status == "ok"


def test_symptom_module_does_not_import_gold_or_hidden_material():
    import ast

    tree = ast.parse(Path(symptom.__file__).read_text("utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not {"gold_symbols", "gold_config_keys", "gold_terms", "mutation"} & names
    assert not any("faultgen" in m or "datasets" in m for m in mods)


# --- evidence representation ------------------------------------------------------------------


def test_static_declaration_is_never_labelled_runtime():
    decl = item(14, "config", "settings.db_host [str] = 'localhost'", "shop_api",
                path="lab/shop_api/app/settings.py", line=14)  # fmt: skip
    scope, basis, origin = evidence_view.evidence_label(decl)
    assert (scope, basis) == ("static", "declared") and "not a runtime value" in origin
    line = evidence_view.render_item(decl)
    assert "static/declared" in line and "lab/shop_api/app/settings.py:14" in line
    assert "runtime" not in line.split("]")[0]


def test_compose_environment_is_declared_not_claimed_as_effective():
    comp = item(32, "compose", "service shop_api\nenvironment: DB_HOST=lab_db", "shop_api",
                path="lab/compose.yaml", line=40)  # fmt: skip
    line = evidence_view.render_item(comp)
    assert "static/declared" in line and "not verified" in line and "lab/compose.yaml:40" in line


def test_container_environment_is_observed_but_not_the_apps_settings_object():
    env = item(7, "config", "DB_HOST=lab_db", "shop_api")  # no path: docker inspect env
    scope, basis, origin = evidence_view.evidence_label(env)
    assert (scope, basis) == ("runtime", "observed") and "not the app's Settings object" in origin


def test_explicit_provenance_fields_win_and_old_bundles_still_render():
    ev = item(1, "config", "X=1", "svc", path="a.py", line=2, scope="runtime", basis="observed",
              origin="custom origin")  # fmt: skip
    assert evidence_view.evidence_label(ev) == ("runtime", "observed", "custom origin")
    old = item(2, "health", "container up")  # no provenance fields at all
    assert "runtime/observed" in evidence_view.render_item(old)


def test_rendering_puts_the_symptom_first_and_keeps_ids():
    sym = symptom.build_symptom({"reproducer": REPRO_RUN})
    ev = symptom.with_symptom(bundle(item(1, "health", "ok"), item(2, "log", "x")), sym)
    lines = evidence_view.render_evidence_v2(ev).splitlines()
    assert lines[0].startswith("[EV-0003 issue") and any(ln.startswith("[EV-0001 ") for ln in lines)


def test_collector_labels_new_items():
    from traceforge.evidence import collector

    assert collector._DECLARED_SRC["scope"] == "static"
    assert collector._DECLARED_COMPOSE["basis"] == "declared"
    assert collector._OBS_ENV["scope"] == "runtime"
    assert "Settings object" in collector._OBS_ENV["origin"]


@pytest.mark.parametrize("k", ["scope", "basis", "origin"])
def test_db_persistence_ignores_the_new_optional_fields(k):
    from traceforge.contracts.evidence import EvidenceItem

    assert k in EvidenceItem.model_fields  # persisted rows exclude them (repository.py)


def test_symptom_text_is_byte_stable_across_runs_despite_object_addresses():
    base = REPRO.replace(
        "At index 1 diff",
        "where 2 = <app.models.Product object at 0x7dfb094fe8d0>.stock\nE     At index 1 diff",
    )
    other = base.replace("0x7dfb094fe8d0", "0x705acf6d9550")
    t1 = [
        i.text()
        for i in symptom.parse_failures(
            result(base, ["test_symptom.py::test_price_1"]), "reproducer"
        )
    ]
    t2 = [
        i.text()
        for i in symptom.parse_failures(
            result(other, ["test_symptom.py::test_price_1"]), "reproducer"
        )
    ]
    assert t1 == t2 and "0x..." in t1[0] and "0x7dfb" not in t1[0]
