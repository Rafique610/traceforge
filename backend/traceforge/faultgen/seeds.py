# ruff: noqa: E501
"""The 4 seed cases (all split 'dev'). Ids are opaque on purpose: `<service>-<nnn>` leaks no class/family."""

from pathlib import Path

from traceforge.faultgen import lab_tree
from traceforge.faultgen.model import CaseDraft
from traceforge.faultgen.templates import code, config, insufficient, runtime


def seed_drafts(lab: Path | None = None) -> list[CaseDraft]:
    lab = lab or lab_tree.repo_root() / "lab"
    return [
        config.make("shop_api-001", field="redis_host", bad_value="redis-broker.internal", lab=lab),
        code.make("shop_api-002", site="quantity_upper_bound", lab=lab),
        runtime.make("shop_api-003", stop=("lab_redis",)),
        insufficient.make("shop_api-004"),
    ]
