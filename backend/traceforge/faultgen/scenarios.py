# ruff: noqa: E501
"""Find scenarios that tell the original tree from a faulty one, by running both.

The probe runs the real shop_api code (in a subprocess, cwd = the tree's service dir) against
in-memory SQLite, so it needs no Docker. The sandbox validator later re-checks every case for real.
"""

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from traceforge.faultgen.generate import materialize
from traceforge.faultgen.lab_tree import base_sha
from traceforge.faultgen.templates.scenario import HELPERS, PROBE, PROBE_WORKER, WORKER_HELPERS

_ORIGINAL: dict[tuple, list] = {}

PRICES_VISIBLE = ["3.20", "7.45", "12.00", "18.75", "24.10", "33.33", "41.60", "49.99", "52.40"]
PRICES_HIDDEN = ["2.85", "6.15", "9.99", "15.50", "21.05", "27.90", "36.25", "50.00", "64.80"]
QTY_VISIBLE = [1, 2, 3, 4]
QTY_HIDDEN = [1, 2, 5, 6]
COUPONS_VISIBLE = [None, None, "bulk20", "Welcome10", "staff50"]
COUPONS_HIDDEN = [None, None, "BULK20", "welcome10 ", "Staff50"]
# (stock on the shelf, quantity ordered); ints >= 3 never shared between the two pools (D31)
STOCK_VISIBLE = [(3, 3), (4, 2), (4, 1), (10, 1), (12, 4), (2, 1), (13, 10), (3, 4)]
STOCK_HIDDEN = [(6, 6), (7, 5), (8, 5), (6, 7), (9, 2), (11, 6), (15, 8), (5, 1)]
# worker jobs: (payload = order id or a raw string, handler failures before success)
JOB_VISIBLE = [(11, 0), (12, 1), (13, 2), (14, 4), ("not json", 0), (15, 0)]
JOB_HIDDEN = [(21, 0), (22, 1), (23, 3), (24, 5), ('{"type": "order_confirmation"}', 0), (25, 2)]


def candidates(kind: str, hidden: bool, n: int = 40, seed: int = 0) -> list[dict]:
    """Deterministic candidate scenarios; visible and hidden draw from disjoint input pools."""
    rnd = random.Random(f"{kind}:{hidden}:{seed}")
    prices = PRICES_HIDDEN if hidden else PRICES_VISIBLE
    qtys = QTY_HIDDEN if hidden else QTY_VISIBLE
    if kind == "stock":
        return [{"stock": s, "qty": q} for s, q in (STOCK_HIDDEN if hidden else STOCK_VISIBLE)]
    if kind == "job":
        return [{"payload": p, "failures": f} for p, f in (JOB_HIDDEN if hidden else JOB_VISIBLE)]
    out = []
    for _ in range(n):
        items = [[rnd.choice(prices), rnd.choice(qtys)] for _ in range(rnd.choice([0, 1, 1, 2, 3]))]
        sc: dict = {"items": items}
        if kind == "price":
            sc["coupon"] = rnd.choice(COUPONS_HIDDEN if hidden else COUPONS_VISIBLE)
        out.append(sc)
    return out


def probe(tree: Path, kind: str, scenarios: list[dict], service: str = "shop_api") -> list:
    worker = kind == "job"
    wd = tree / "lab" if worker else tree / "lab" / service  # worker imports itself as `worker.*`
    script = wd / "_probe_tf.py"
    script.write_text(
        WORKER_HELPERS + PROBE_WORKER if worker else HELPERS + PROBE, encoding="utf-8"
    )
    env = {
        k: v for k, v in os.environ.items() if not k.startswith(("DB_", "REDIS_", "TRACEFORGE_"))
    }
    env.update(DB_USER="shopper", DB_PASSWORD="unused", PYTHONDONTWRITEBYTECODE="1")
    try:
        r = subprocess.run(  # noqa: S603
            [sys.executable, script.name], cwd=wd, input=json.dumps([kind, scenarios]),
            capture_output=True, text=True, timeout=120, env=env,
        )  # fmt: skip
    finally:
        script.unlink(missing_ok=True)
    if r.returncode:
        raise RuntimeError(f"probe failed: {r.stderr[-1500:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def discriminating(
    lab: Path, patch: str, kind: str, hidden: bool, want: int
) -> tuple[list[dict], list]:
    """Up to `want` scenarios whose observation differs between original and faulty tree.

    Returns (scenarios, expected observations on the original). Scenarios where the original itself
    errors are never used."""
    cands = candidates(kind, hidden)
    work = Path(tempfile.mkdtemp(prefix="tf-scen-"))
    try:
        key = (base_sha(lab), kind, hidden)
        if key not in _ORIGINAL:  # the original tree's answers are the same for every variant
            _ORIGINAL[key] = probe(materialize("", work / "o", lab), kind, cands)
        orig = _ORIGINAL[key]
        try:
            bad = probe(materialize(patch, work / "b", lab), kind, cands)
        except RuntimeError:  # faulty tree does not even import (e.g. a bad default at class level)
            bad = [["error", "app_fails_to_load"]] * len(cands)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    picked, expected, seen = [], [], set()
    for sc, o, b in zip(cands, orig, bad, strict=True):
        key = json.dumps(sc, sort_keys=True)
        if o and o[0] != "error" and o != b and key not in seen:
            seen.add(key)
            picked.append(sc)
            expected.append(o)
        if len(picked) == want:
            break
    return picked, expected
