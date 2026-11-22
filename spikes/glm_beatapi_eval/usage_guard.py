"""Read-only BeatAPI usage check. Any paid usage or any other model aborts the whole run."""

from __future__ import annotations

import json
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

USAGE_URL = "https://api.beatapi.io/v1/usage"  # read-only, free
FREE_MODEL = "glm-5.3-flash-free"


class UsageAnomaly(RuntimeError):
    """Paid usage, a different model, or an unreadable usage endpoint: STOP everything."""


def fetch_usage(key: str) -> dict:
    req = urllib.request.Request(
        USAGE_URL, headers={"Authorization": "Bearer " + key, "User-Agent": "tf-eval/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:  # GET only
        return json.loads(r.read().decode("utf-8"))


def violations(payload: dict) -> list[str]:
    d = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(d, dict):
        return ["usage payload has no 'data' object"]
    bad = []
    if d.get("credit_balance") != 0:
        bad.append(f"credit_balance={d.get('credit_balance')!r} (expected 0)")
    if d.get("credits_settled") != 0:
        bad.append(f"credits_settled={d.get('credits_settled')!r} (expected 0)")
    for m in d.get("by_model") or []:
        if m.get("model") != FREE_MODEL:
            bad.append(f"other model in by_model: {m.get('model')!r}")
        if m.get("credits_settled") != 0:
            bad.append(f"model {m.get('model')!r} credits_settled={m.get('credits_settled')!r}")
    return bad


class UsageGuard:
    def __init__(self, fetch: Callable[[], dict], snapshot_file: Path | None = None):
        self.fetch = fetch
        self.snapshot_file = snapshot_file
        self.snapshots: list[dict] = []

    def check(self, label: str) -> dict:
        try:
            payload = self.fetch()
        except Exception as e:  # cannot verify == cannot continue
            raise UsageAnomaly(f"usage endpoint unreadable at {label}: {type(e).__name__}") from e
        d = payload.get("data", {}) if isinstance(payload, dict) else {}
        snap = {"label": label, "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "credit_balance": d.get("credit_balance"),
                "credits_settled": d.get("credits_settled"),
                "total_tasks": d.get("total_tasks"),
                "by_model": d.get("by_model")}  # no api-key fields, no secrets
        self.snapshots.append(snap)
        if self.snapshot_file:
            self.snapshot_file.write_text(json.dumps(self.snapshots, indent=1), encoding="utf-8")
        bad = violations(payload)
        if bad:
            snap["violations"] = bad
            raise UsageAnomaly(f"usage anomaly at {label}: {'; '.join(bad)}")
        return snap
