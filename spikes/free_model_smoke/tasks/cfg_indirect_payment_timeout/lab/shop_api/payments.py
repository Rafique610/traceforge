"""Payment gateway client (simulated gateway answers in about 250 ms)."""
from pathlib import Path


def load_settings(root=None):
    root = Path(root) if root else Path(__file__).parent
    out = {}
    for line in (root / "settings.env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            out[key] = value
    return out

GATEWAY_LATENCY_S = 0.25


class PaymentTimeout(Exception):
    pass


def _remote_charge(amount_cents, timeout_s, latency_s=GATEWAY_LATENCY_S):
    if latency_s > timeout_s:
        raise PaymentTimeout(f"payment gateway did not answer within {timeout_s:.3f}s")
    return {"status": "ok", "amount": amount_cents}


def charge(amount_cents, settings):
    timeout_s = int(settings["PAYMENT_TIMEOUT_MS"]) / 1000
    return _remote_charge(amount_cents, timeout_s)
