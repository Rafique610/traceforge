# ruff: noqa: E501
"""Scenario-tested fault sites in shop_api (code faults and wrong settings defaults).

A site = one line in the lab that a real developer could get wrong, plus up to five realistic wrong
versions of it (`variants`). All variants of a site share one variant_group, so they always land in
the same split. Reproducer and hidden tests are found by `scenarios.discriminating` and use disjoint
inputs (D31). `distance` is a manual estimate: hops from the failing endpoint handler to the site.
"""

from traceforge.faultgen import lab_tree
from traceforge.faultgen.model import CaseDraft
from traceforge.faultgen.scenarios import discriminating
from traceforge.faultgen.templates.api_stub import api_conftest
from traceforge.faultgen.templates.scenario import (
    HELPERS,
    WORKER_HELPERS,
    render_tests,
    render_worker_tests,
)
from traceforge.faultgen.templates.site_data import CODE_SITES, CONFIG_SITES, S
from traceforge.faultgen.templates.worker_site_data import WORKER_CODE_SITES, WORKER_CONFIG_SITES

DOC = {
    "price": "Price rules: what a customer is charged for an order.",
    "total": "Order totals and counts as shown on the order summary.",
    "stock": "Shelf stock: orders take units off the shelf; low shelves are reported.",
    "job": "Order confirmation jobs: retries, backoff and dead letters.",
}
# hidden files get their own docstring: a shared docstring counts as a shared input literal (D31)
HIDDEN_DOC = "Acceptance checks. "
SETTINGS = {"shop_api": (S, "Settings"), "worker": ("lab/worker/settings.py", "WorkerSettings")}


def _suites(kind: str, vis, vis_exp, hid, hid_exp) -> tuple[dict, dict]:
    if kind == "job":
        return (
            {"conftest.py": WORKER_HELPERS, "test_symptom.py": render_worker_tests(vis, vis_exp, DOC[kind])},
            {"conftest.py": WORKER_HELPERS, "test_hidden_behaviour.py": render_worker_tests(hid, hid_exp, HIDDEN_DOC + DOC[kind])},
        )  # fmt: skip
    return (
        {"conftest.py": api_conftest() + HELPERS, "test_symptom.py": render_tests(kind, vis, vis_exp, DOC[kind])},
        {"conftest.py": api_conftest(("Lid", "1.15"), ("Jar", "6.35")) + HELPERS,
         "test_hidden_behaviour.py": render_tests(kind, hid, hid_exp, HIDDEN_DOC + DOC[kind])},
    )  # fmt: skip


def _draft(case_id, cls, family, group, kind, path, new_text, qual, distance, log_format, params, lab,
           service="shop_api", gold_keys=(), allowed=None, notes="") -> CaseDraft | None:  # fmt: skip
    patch = _patch(lab, path, new_text)
    vis, vis_exp = discriminating(lab, patch, kind, hidden=False, want=2)
    hid, hid_exp = discriminating(lab, patch, kind, hidden=True, want=3)
    if not vis or not hid:
        return None  # this wrong version is not observable through the public behaviour: drop it
    repro, hidden = _suites(kind, vis, vis_exp, hid, hid_exp)
    return CaseDraft(
        case_id=case_id, cause_class=cls, fault_family=family, service=service, variant_group=group,
        log_format=log_format, distance=distance, template=f"sites.{kind}", params=params,
        edits={path: new_text}, gold_config_keys=list(gold_keys), gold_symbols=[(path, qual)],
        reproducer_files=repro, hidden_files=hidden, allowed_terms=allowed or {},
        notes=notes or "distance: manual estimate (hops from the failing entry point to the site)",
    )  # fmt: skip


def _patch(lab, path: str, new_text: str) -> str:
    from traceforge.faultgen.patching import make_patch

    return make_patch({path: (lab_tree.read_lf(lab.parent / path), new_text)})


def _code_table(service: str) -> dict:
    return WORKER_CODE_SITES if service == "worker" else CODE_SITES


def code_variants(site: str, lab, service: str = "shop_api") -> list[tuple[dict, str]]:
    s = _code_table(service)[site]
    text = lab_tree.read_lf(lab.parent / s["path"])
    if text.count(s["old"]) != 1:
        raise ValueError(f"{s['path']}: expected exactly one line {s['old']!r}")
    return [
        ({"site": site, "variant": i}, text.replace(s["old"], v))
        for i, v in enumerate(s["variants"])
    ]


def make_code(
    case_id: str, site: str, variant: int, lab, log_format: str, service: str = "shop_api"
) -> CaseDraft | None:
    s = _code_table(service)[site]
    params, new_text = code_variants(site, lab, service)[variant]
    return _draft(case_id, "application_code", s["family"], f"code:{service}:{site}" if service == "worker" else f"code:{site}",
                  s["kind"], s["path"], new_text, s["qual"], s["distance"], log_format, params, lab,
                  service=service, allowed=s.get("allowed"))  # fmt: skip


def make_config(
    case_id: str, field: str, variant: int, lab, log_format: str, service: str = "shop_api"
) -> CaseDraft | None:
    c = (WORKER_CONFIG_SITES if service == "worker" else CONFIG_SITES)[field]
    path, cls = SETTINGS[service]
    text = lab_tree.read_lf(lab.parent / path)
    old = c["line"].replace("@@", c["good"])
    if text.count(old) != 1:
        raise ValueError(f"{path}: expected exactly one line {old!r}")
    bad = c["bad"][variant]
    return _draft(case_id, "configuration", c["family"], f"settings_default:{service}:{field}", c["kind"], path,
                  text.replace(old, c["line"].replace("@@", bad)), f"{cls}.{field}", 1, log_format,
                  {"field": field, "bad_value": bad, "service": service}, lab, service=service,
                  gold_keys=[f"{service}.{field.upper()}"],
                  notes="distance 1 (manual): the failing code reads the field; the wrong value is its default")  # fmt: skip
