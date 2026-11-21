"""On-disk response cache: one JSON file per canonical request hash."""

import hashlib
import json
from pathlib import Path
from typing import Any


def cache_key(request: dict[str, Any]) -> str:
    canon = json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode()).hexdigest()


def _path(root: Path, provider: str, model: str, key: str) -> Path:
    return root / provider / model.replace("/", "_").replace(":", "_") / key[:2] / f"{key}.json"


def get(root: Path, provider: str, model: str, key: str) -> dict[str, Any] | None:
    path = _path(root, provider, model, key)
    return json.loads(path.read_text("utf-8"))["response"] if path.exists() else None


def put(root: Path, provider: str, model: str, key: str, request: dict, response: dict) -> None:
    path = _path(root, provider, model, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"request": request, "response": response}), "utf-8")
