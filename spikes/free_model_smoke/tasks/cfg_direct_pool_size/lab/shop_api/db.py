"""Connection pool for the shop database."""
from pathlib import Path


def load_settings(root=None):
    root = Path(root) if root else Path(__file__).parent
    out = {}
    for line in (root / "settings.env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            out[key] = value
    return out


class Pool:
    def __init__(self, size, timeout_s):
        self.size = size
        self.timeout_s = timeout_s


def make_pool(settings=None):
    s = settings or load_settings()
    size = int(s["DB_POOL_SIZE"])
    if size < 1:
        raise ValueError(f"DB_POOL_SIZE must be >= 1, got {size}")
    return Pool(size, float(s["DB_POOL_TIMEOUT_S"]))
