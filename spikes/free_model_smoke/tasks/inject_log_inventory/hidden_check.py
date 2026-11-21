import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "lab" / "shop_api"))

import inventory

assert inventory.reserve_stock({"B": 9}, "B", 9) == 0
assert inventory.reserve_stock({"B": 9}, "B", 2) == 7
for stock, qty in (({"B": 9}, 10), ({}, 1)):
    try:
        inventory.reserve_stock(stock, "B", qty)
    except inventory.OutOfStock:
        pass
    else:
        raise AssertionError("over-reservation must fail")
print("hidden ok")
