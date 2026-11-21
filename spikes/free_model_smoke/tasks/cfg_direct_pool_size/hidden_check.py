import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "lab" / "shop_api"))

import db

s = db.load_settings(ROOT / "lab" / "shop_api")
pool = db.make_pool(s)
assert 1 <= pool.size <= 100, pool.size
assert s["DB_POOL_TIMEOUT_S"] == "10" and s["APP_ENV"] == "production"
assert s["DB_URL"] == "postgresql://shop:***@db:5432/shop"
print("hidden ok")
