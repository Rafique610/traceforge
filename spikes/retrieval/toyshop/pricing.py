"""Prices, discounts and tax."""

from settings import settings


def line_total(price, qty):
    return price * qty


def unit_price(total, qty):
    return total / qty if qty else 0.0


def apply_discount(amount, fraction):
    cap = settings().discount_cap
    return amount * (1 - min(fraction, cap))


def add_tax(amount):
    return round(amount * (1 + settings().tax_rate), 2)
