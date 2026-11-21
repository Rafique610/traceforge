import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "lab" / "shop_api"))

import orders
import tax

assert abs(tax.compute_tax(19.99, "NY") - 1.6) < 0.005
assert abs(tax.compute_tax(250.0, "TX") - 15.625) < 0.006
assert tax.compute_tax(10, "ZZ") == 0
inv = orders.build_invoice([(19.99, 3), (5.0, 2)], "NY", 75.57)
assert abs(inv["total"] - 75.57) < 0.005, inv
print("hidden ok")
