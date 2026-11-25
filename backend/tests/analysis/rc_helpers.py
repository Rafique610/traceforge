# ruff: noqa: E501
"""Helpers: tiny synthetic project (NOT a benchmark fixture) for unit tests of the analysis package."""

import os
import subprocess
import sys
from pathlib import Path

FILES = {
    "core.py": """class Base:
    def run(self, x):
        return self.helper(x)

    def helper(self, x):
        return x


class Child(Base):
    def run(self, x):
        return x + 1
""",
    "util.py": "def norm(x):\n    return x\n",
    "svc.py": """import core
from core import Base, Child
from external_lib import Remote


class Mixin(core.Base):
    pass


class Ext(Remote):
    pass


class GrandChild(Child):
    def helper(self, x):
        return x * 2


def go(obj, v):
    return obj.run(v)


def dyn(name):
    return getattr(core, name)()


def plain(v):
    return Base().run(v)
""",
    "cfg.py": 'import os\n\nHOST = os.getenv("HOST", "h")\nPASSWORD = os.getenv("DB_PASSWORD", "hunter2")\nPORT = int(os.getenv("PORT", "80"))\n',
    "api.py": "import cfg\nfrom util import norm\n\n\ndef addr():\n    return norm(cfg.HOST)\n\n\ndef port():\n    return cfg.PORT\n",
    "compose.yaml": "services:\n  web:\n    build: .\n    command: python -m api\n    environment:\n      HOST: x\n      DB_PASSWORD: s3cret\n",
    "tests/test_core.py": "from core import Base, Child\n\n\ndef test_base():\n    b = Base()\n    assert b.run(1) == 1\n\n\ndef test_child():\n    c = Child()\n    assert c.run(1) == 2\n",
    "tests/test_api.py": "from api import addr\n\n\ndef test_addr():\n    assert addr() == 'x'\n",
    "tests/test_svc.py": "from svc import plain\n\n\ndef test_plain():\n    assert plain(1) == 1\n",
    "tests_hidden/test_h.py": "from core import Base\n\n\ndef test_hidden_base():\n    b = Base()\n    assert b.run(3) == 3\n",
}
VISIBLE = [
    "tests/test_core.py::test_base",
    "tests/test_core.py::test_child",
    "tests/test_api.py::test_addr",
    "tests/test_svc.py::test_plain",
]


def write_tree(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    return root


def patched_copy(tmp_path: Path, edits: dict[str, tuple[str, str]], name: str = "patched") -> Path:
    files = dict(FILES)
    for rel, (old, new) in edits.items():
        assert files[rel].count(old) == 1, (rel, old)
        files[rel] = files[rel].replace(old, new)
    return write_tree(tmp_path / name, files)


def run_pytest(root: Path, targets) -> tuple[int, int, list[str]]:
    env = {"PATH": os.environ.get("PATH", ""), "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
           "PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1"}  # fmt: skip
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", *targets],
        cwd=root, capture_output=True, text=True, timeout=120, env=env,
    )  # fmt: skip
    import re

    rows = re.findall(r"^(PASSED|FAILED|ERROR) (\S+)", p.stdout, re.M)
    return (
        sum(1 for k, _ in rows if k == "PASSED"),
        sum(1 for k, _ in rows if k != "PASSED"),
        [i for k, i in rows if k != "PASSED"],
    )
