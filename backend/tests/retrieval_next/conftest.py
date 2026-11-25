# ruff: noqa: E501
import os
from pathlib import Path

os.environ.setdefault("TF_RETNEXT_NO_AUTOREGISTER", "1")  # tests register with a fake embedder

import pytest  # noqa: E402

from traceforge.retrieval_bench.repo_ctx import build_context  # noqa: E402

SRC = {
    "pkg/__init__.py": "",
    "pkg/billing.py": (
        "def compute_tax(amount, rate):\n    return amount * rate\n\n\n"
        "def apply_discount(amount, pct):\n    return amount * (100 - pct) / 100\n"
    ),
    "pkg/queue.py": (
        "class JobQueue:\n    def push(self, job):\n        raise ConnectionError('broker down')\n\n"
        "    def pop(self):\n        return None\n"
    ),
    "pkg/settings.py": "REDIS_HOST = 'localhost'\nMAX_RETRIES = 3\n",
}


@pytest.fixture()
def tiny_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for rel, text in SRC.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, "utf-8")
    return root


@pytest.fixture()
def tiny_ctx(tiny_repo):
    return build_context("tiny", tiny_repo)
