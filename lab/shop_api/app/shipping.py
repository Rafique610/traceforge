"""Shipping and tax on an order amount."""

from decimal import Decimal

from app.pricing import ZERO, money


def shipping_fee(amount: Decimal, fee: Decimal, free_over: Decimal) -> Decimal:
    """Flat fee, waived when the (discounted) amount reaches the free-shipping threshold."""
    return ZERO if amount >= free_over else money(fee)


def tax_amount(amount: Decimal, rate: Decimal) -> Decimal:
    """Sales tax on goods only (shipping is not taxed)."""
    return money(amount * rate)
