# ruff: noqa: E501
"""The full case catalogue: seed cases + every site variant, with a fixed dev/test split by group.

Split rule (ml.md, D-split): whole variant groups go to one split. DEV_GROUPS is fixed here, before any
tuning, so the test split never depends on results. Case ids are opaque (`shop_api-NNN`) and assigned
in a seeded shuffle, so an id reveals neither class nor family.
"""

import random
from pathlib import Path

from traceforge.faultgen.model import CaseDraft
from traceforge.faultgen.seeds import seed_drafts
from traceforge.faultgen.templates import code, config, sites

DEV_GROUPS = {
    "code:total_loop", "code:tax_base", "code:stock_decrement", "code:discount_formula",
    "settings_default:shop_api:max_discount_pct", "settings_default:shop_api:low_stock_level",
}  # fmt: skip
REDIS_BAD = {
    "redis_host": ["lab-redis", "redis.local", "redis-cache"],
    "redis_port": ["6380", "63790", "7379"],
}
SEED_IDS = 4  # shop_api-001..004 keep their ids and stay in dev


def _specs() -> list[tuple]:
    """(kind, site/field, variant, log_format) for every candidate case beyond the seeds."""
    out = []
    for site, s in sites.CODE_SITES.items():
        out += [("code", site, i, "uvicorn_access") for i in range(len(s["variants"]))]
    for field, c in sites.CONFIG_SITES.items():
        out += [("config", field, i, "plain") for i in range(len(c["bad"]))]
    for site in code.SITES:
        if site != "quantity_upper_bound":  # already a seed
            out.append(("legacy_code", site, 0, "uvicorn_access"))
    for field, bads in REDIS_BAD.items():
        out += [("redis", field, b, "plain") for b in bads]
    return out


def _make(case_id: str, spec: tuple, lab: Path) -> CaseDraft | None:
    kind, name, variant, log = spec
    if kind == "code":
        return sites.make_code(case_id, name, variant, lab, log)
    if kind == "config":
        return sites.make_config(case_id, name, variant, lab, log)
    if kind == "legacy_code":
        return code.make(case_id, site=name, lab=lab)
    return config.make(case_id, field=name, bad_value=variant, log_format=log, lab=lab)


def all_drafts(lab: Path) -> list[tuple[CaseDraft, str]]:
    """Every case with its split. Unobservable variants are dropped (reported by the caller)."""
    out = [(d, "dev") for d in seed_drafts(lab)]
    specs = _specs()
    random.Random(20261122).shuffle(specs)
    n = SEED_IDS
    for spec in specs:
        d = _make(f"shop_api-{n + 1:03d}", spec, lab)
        if d is None:
            print(f"dropped (not observable): {spec}")
            continue
        n += 1
        out.append((d, "dev" if d.variant_group in DEV_GROUPS else "test"))
    return out
