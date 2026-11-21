"""Append-only call log: hashes and counts only, never message content or secrets."""

import json
import time
from pathlib import Path


def log_call(path: Path, **fields: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), **fields}) + "\n")
