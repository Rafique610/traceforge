import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "lab" / "shop_api"))

import payments

s = payments.load_settings(ROOT / "lab" / "shop_api")
assert payments.charge(500, s)["status"] == "ok"
print("visible ok")
