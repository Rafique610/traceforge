"""Coupon codes: parsed from settings, capped, and only valid until a configured date."""

from datetime import date
from decimal import Decimal

from app.pricing import money


class UnknownCoupon(LookupError):
    pass


class ExpiredCoupon(ValueError):
    pass


def parse_codes(raw: str) -> dict[str, int]:
    """'WELCOME10=10,BULK20=20' -> {'WELCOME10': 10, 'BULK20': 20}. Blank entries are skipped."""
    codes: dict[str, int] = {}
    for entry in raw.split(","):
        if not entry.strip():
            continue
        code, pct = entry.split("=", 1)
        codes[code.strip().upper()] = int(pct)
    return codes


def valid_until(raw: str) -> date:
    return date.fromisoformat(raw)


def discount_pct(code: str, codes: dict[str, int], cap: int, expires: date, today: date) -> int:
    """Percentage for `code` (case-insensitive), never above `cap`."""
    if today > expires:
        raise ExpiredCoupon(code)
    pct = codes.get(code.strip().upper())
    if pct is None:
        raise UnknownCoupon(code)
    return min(pct, cap)


def apply_discount(amount: Decimal, pct: int) -> Decimal:
    return money(amount * (100 - pct) / 100)
