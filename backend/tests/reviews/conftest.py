"""Reuse the report fixtures."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "reports"))

from support import client, db, session_factory  # noqa: E402,F401
