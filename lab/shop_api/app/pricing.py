"""Money arithmetic helpers. Pure functions, no DB."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal) -> Decimal:
    """Round to 2 dp, half up."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def line_total(unit_price: Decimal, quantity: int) -> Decimal:
    return money(unit_price * quantity)


def average_unit_price(total: Decimal, quantity: int) -> Decimal:
    """Average price per unit across an order (total / units)."""
    return money(total / quantity)
