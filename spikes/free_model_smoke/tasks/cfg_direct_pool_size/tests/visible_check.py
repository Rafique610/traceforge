import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "lab" / "shop_api"))

import db

pool = db.make_pool(db.load_settings(ROOT / "lab" / "shop_api"))
assert pool.size >= 1
print("visible ok")
