# ruff: noqa: E501
"""Pipeline v5 patch scope and target handoff: an edit may touch only the diagnosed fault."""

from types import SimpleNamespace as N

from conftest import CORRECT, real_runner

from traceforge.agent.handoff import validate_target
from traceforge.agent.tools import SubmitDiagnosis, ToolContext
from traceforge.repair import run_repair
from traceforge.repair.scope import REASON, make_scope_check, symbol_range

SETTINGS = (
    "class Settings:\n"
    '    redis_host: str = "localhost"\n'
    "    redis_port: int = 7379\n"
    "    tax_rate: float = 0.17\n"
)
CODE = (
    "def total(items):\n    return sum(items[1:])\n\n\n"
    "def other(x):\n    return x + 1\n\n\n"
    "class Box:\n    def size(self):\n        return 1\n"
)


def cfg(key):
    return SubmitDiagnosis(
        cause_class="configuration", config_key=key, supporting_evidence_ids=["EV-0001"]
    )


def code(path, qual):
    return SubmitDiagnosis(
        cause_class="application_code",
        path=path,
        qualname=qual,
        supporting_evidence_ids=["EV-0001"],
    )


# --- configuration scope (the shop_api-013 over-edit) -----------------------------------------


def test_fixing_only_the_diagnosed_key_is_allowed():
    check = make_scope_check(cfg("shop_api.REDIS_PORT"))
    new = SETTINGS.replace("7379", "6379")
    assert check({"s.py": SETTINGS}, {"s.py": new}) == []


def test_the_013_over_edit_of_an_unrelated_default_is_rejected():
    check = make_scope_check(cfg("shop_api.REDIS_PORT"))
    new = SETTINGS.replace("7379", "6379").replace('"localhost"', '"lab_redis"')  # host + port
    reasons = check({"s.py": SETTINGS}, {"s.py": new})
    assert reasons and reasons[0].startswith(REASON) and ":s.py:2" in reasons[0]


def test_inserting_an_unrelated_line_is_rejected_and_a_related_one_allowed():
    check = make_scope_check(cfg("shop_api.TAX_RATE"))
    assert check({"s.py": SETTINGS}, {"s.py": SETTINGS + "    other_flag: bool = True\n"})
    assert check({"s.py": SETTINGS}, {"s.py": SETTINGS + "    tax_rate_note: str = ''\n"}) == []


# --- code scope --------------------------------------------------------------------------------


def test_edit_inside_the_diagnosed_function_is_allowed_and_elsewhere_rejected():
    check = make_scope_check(code("m.py", "total"))
    inside = CODE.replace("items[1:]", "items")
    assert check({"m.py": CODE}, {"m.py": inside}) == []
    outside = CODE.replace("x + 1", "x + 2")
    assert check({"m.py": CODE}, {"m.py": outside})[0].startswith(REASON)


def test_edit_in_another_file_is_rejected_for_a_code_diagnosis():
    check = make_scope_check(code("m.py", "total"))
    reasons = check(
        {"m.py": CODE, "n.py": "x = 1\n"}, {"m.py": CODE.replace("[1:]", ""), "n.py": "x = 2\n"}
    )
    assert reasons == [f"{REASON}:n.py"]


def test_methods_and_class_fields_resolve_and_unresolvable_symbols_are_not_guessed():
    assert symbol_range(CODE, "Box.size") == (10, 11)
    assert symbol_range(SETTINGS, "Settings.redis_port") == (3, 3)
    assert symbol_range(CODE, "nope") is None
    check = make_scope_check(code("m.py", "nope"))
    assert check({"m.py": CODE}, {"m.py": CODE.replace("x + 1", "x")}) == []  # validated earlier


def test_no_diagnosis_means_no_scope_check():
    assert make_scope_check(None) is None


# --- the repair loop applies it --------------------------------------------------------------


def test_loop_rejects_an_out_of_scope_edit_and_records_the_reason(repo):
    path, sha = repo

    def scope(old, new):
        return [f"{REASON}:shop.py:1"]

    seen = []

    def propose(_ctx, _fb):
        seen.append(1)
        return CORRECT

    r = run_repair(
        case_id="c", repo_path=path, base_sha=sha, condition="F0", context=None,
        propose_edit=propose, run_tests=real_runner, allowlist=["shop.py"], scope_check=scope,
    )  # fmt: skip
    assert len(seen) == 3 and r.outcome == "REJECTED"  # every attempt is rejected, none is run
    assert all(a.reasons == [f"{REASON}:shop.py:1"] and a.diff is None for a in r.attempts)


def test_loop_without_a_scope_check_behaves_as_before(repo):
    path, sha = repo
    r = run_repair(
        case_id="c", repo_path=path, base_sha=sha, condition="F0", context=None,
        propose_edit=lambda c, f: CORRECT, run_tests=real_runner, allowlist=["shop.py"],
    )  # fmt: skip
    assert r.outcome == "TEST_VERIFIED_IN_LAB"


# --- target validation before any patch -----------------------------------------------------


class Ctx:
    def __init__(self, known=True):
        self.known = known

    def read_symbol(self, case, path, qualname):
        return "src" if self.known else None


def tcx(known=True, text="REDIS_PORT=6379"):
    ev = N(items=[N(id="EV-0001", content=text)])
    case = N(service="shop_api")
    t = ToolContext.__new__(ToolContext)
    t.case, t.evidence, t.ctx, t.v5 = case, ev, Ctx(known), True
    return t


def test_validate_target_accepts_supported_targets_and_skips_non_repairable():
    assert validate_target(tcx(), code("lab/shop_api/app/m.py", "f")) is None
    assert validate_target(tcx(), cfg("shop_api.REDIS_PORT")) is None
    assert validate_target(tcx(), SubmitDiagnosis(cause_class="runtime_dependency",
                                                  supporting_evidence_ids=["EV-0001"])) is None  # fmt: skip
    assert validate_target(tcx(), None) is None


def test_validate_target_refuses_unpermitted_missing_or_unsupported_targets():
    assert "path not permitted" in validate_target(tcx(), code("lab/worker/q.py", "f"))
    assert "symbol not found" in validate_target(tcx(False), code("lab/shop_api/app/m.py", "f"))
    assert "not in evidence" in validate_target(tcx(), cfg("shop_api.UNKNOWN_KEY"))


def test_each_attempt_records_per_test_outcomes_for_regression_checks(repo):
    path, sha = repo
    r = run_repair(
        case_id="c", repo_path=path, base_sha=sha, condition="F0", context=None,
        propose_edit=lambda c, f: CORRECT, run_tests=real_runner, allowlist=["shop.py"],
    )  # fmt: skip
    att = r.attempts[0]
    assert att.visible_outcomes and set(att.visible_outcomes.values()) == {"passed"}
    assert att.reproducer_outcomes and all(o == "passed" for o in att.reproducer_outcomes.values())
