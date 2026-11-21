import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "lab" / "shop_api"))

import pricing

assert pricing.apply_discount(200, 25) == 150.0
assert pricing.apply_discount(99.99, 0) == 99.99
assert pricing.apply_discount(50, 100) == 0
assert pricing.line_total(19.99, 3, 10) == 53.97
try:
    pricing.apply_discount(10, 120)
except ValueError:
    pass
else:
    raise AssertionError("percent > 100 must still be rejected")
print("hidden ok")
