import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "lab" / "shop_api"))

import pricing

assert pricing.apply_discount(100, 10) == 90.0
print("visible ok")
