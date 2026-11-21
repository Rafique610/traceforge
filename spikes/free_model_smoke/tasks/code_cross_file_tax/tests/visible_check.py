import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "lab" / "shop_api"))

import orders

assert orders.build_invoice([(100.0, 1)], "CA", 107.25)["total"] == 107.25
print("visible ok")
