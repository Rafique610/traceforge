"""Catalogue invariants (no probe runs): disjoint input pools, valid dev groups, exact sites."""

from traceforge.faultgen import catalogue, lab_tree, scenarios
from traceforge.faultgen.templates import sites

LAB = lab_tree.repo_root() / "lab"


def _big(values):
    return {v for v in values if isinstance(v, str) or abs(v) >= 3}


def test_visible_and_hidden_pools_share_no_input():
    assert not set(scenarios.PRICES_VISIBLE) & set(scenarios.PRICES_HIDDEN)
    assert not _big(scenarios.QTY_VISIBLE) & _big(scenarios.QTY_HIDDEN)
    assert not {c for c in scenarios.COUPONS_VISIBLE if c} & {
        c for c in scenarios.COUPONS_HIDDEN if c
    }
    vis = _big(n for pair in scenarios.STOCK_VISIBLE for n in pair)
    hid = _big(n for pair in scenarios.STOCK_HIDDEN for n in pair)
    assert not vis & hid


def test_candidates_are_deterministic():
    assert scenarios.candidates("price", False) == scenarios.candidates("price", False)


def test_every_site_line_exists_exactly_once_in_the_lab():
    for site in sites.CODE_SITES:
        assert len(sites.code_variants(site, LAB)) == len(sites.CODE_SITES[site]["variants"])
    text = lab_tree.read_lf(LAB.parent / sites.S)
    for c in sites.CONFIG_SITES.values():
        assert text.count(c["line"].replace("@@", c["good"])) == 1


def test_dev_groups_are_real_groups():
    groups = (
        {f"code:{s}" for s in sites.CODE_SITES}
        | {f"settings_default:shop_api:{f}" for f in sites.CONFIG_SITES}
        | {f"code:worker:{s}" for s in sites.WORKER_CODE_SITES}
        | {f"settings_default:worker:{f}" for f in sites.WORKER_CONFIG_SITES}
    )
    assert catalogue.DEV_GROUPS <= groups


def test_rendered_tests_are_valid_python():
    """Expected values must render as Python literals (True, None), never JSON (true, null)."""
    from traceforge.faultgen.templates.scenario import render_tests, render_worker_tests

    src = render_tests("stock", [{"stock": 4, "qty": 1}], [[201, 3, True]], "doc")
    compile(src, "t.py", "exec")
    assert "True" in src and "true" not in src
    wsrc = render_worker_tests(
        [{"payload": "not json", "failures": 0}], [[False, 0, [], 1, 0]], "doc"
    )
    compile(wsrc, "w.py", "exec")
    assert "False" in wsrc and "false" not in wsrc
