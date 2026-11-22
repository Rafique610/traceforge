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
    groups = {f"code:{s}" for s in sites.CODE_SITES} | {
        f"settings_default:shop_api:{f}" for f in sites.CONFIG_SITES
    }
    assert catalogue.DEV_GROUPS <= groups
