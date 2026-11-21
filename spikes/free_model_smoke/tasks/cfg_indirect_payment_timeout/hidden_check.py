import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "lab" / "shop_api"))

import payments

s = payments.load_settings(ROOT / "lab" / "shop_api")
ms = int(s["PAYMENT_TIMEOUT_MS"])
assert 250 <= ms <= 30000, ms
assert payments.charge(12345, s)["amount"] == 12345
assert s["SHIPPING_TIMEOUT_MS"] == "3000" and s["RETRY_MAX"] == "2"
assert s["PAYMENT_BASE_URL"] == "http://payments:8080"
print("hidden ok")
