import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "lab" / "shop_api"))

import inventory

assert inventory.reserve_stock({"A-17": 5}, "A-17", 5) == 0
print("visible ok")
