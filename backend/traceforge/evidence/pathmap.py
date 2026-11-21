"""Map container paths to repo-relative POSIX paths (contract: no backslashes, no drive colon)."""

from pathlib import Path

from traceforge.evidence.model import EvidenceConfig


def to_repo_path(path: str, service: str, cfg: EvidenceConfig) -> str | None:
    """Repo-relative path for a container path, or None when not repo code (or not found)."""
    p = path.replace("\\", "/")
    if "/lab/" in p and p.startswith("/app/"):  # /app/lab/shop_api/app/x.py
        rel = p[len("/app/") :]
    else:
        prefix = cfg.path_map.get(service)
        if not prefix or not p.startswith(prefix[0]):
            return None
        rel = prefix[1] + p[len(prefix[0]) :]
    rel = str(Path(rel).as_posix()).lstrip("/")
    if ".." in rel.split("/") or ":" in rel:
        return None
    return rel if (cfg.repo_root / rel).is_file() else None
