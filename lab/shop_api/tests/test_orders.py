"""Visible tests for order/pricing logic (contract: CONTRACT.md)."""

from decimal import Decimal

import pytest
from app.models import OrderItem
from app.orders import order_average_price, order_headline, order_total, unit_count
from app.pricing import average_unit_price, line_total, money


def item(price: str, qty: int, name: str = "x") -> OrderItem:
    return OrderItem(product_name=name, unit_price=Decimal(price), quantity=qty)


def test_checkout_total():
    items = [item("7.25", 2), item("18.50", 1)]
    assert order_total(items) == Decimal("33.00")


def test_total_rounds_half_up_to_two_places():
    assert order_total([item("0.335", 1)]) == Decimal("0.34")
    assert money(Decimal("2.675")) == Decimal("2.68")


def test_empty_order_total_is_zero():
    assert order_total([]) == Decimal("0.00")


def test_line_total_multiplies():
    assert line_total(Decimal("3.99"), 3) == Decimal("11.97")


def test_headline_and_counts():
    items = [item("1.00", 2, "Mug"), item("2.00", 3, "Beans")]
    assert order_headline(items) == "Mug"
    assert order_headline([]) is None
    assert unit_count(items) == 5


def test_average_unit_price():
    assert average_unit_price(Decimal("10.00"), 4) == Decimal("2.50")
    assert order_average_price([]) == Decimal("0.00")
    assert order_average_price([item("2.00", 1), item("4.00", 1)]) == Decimal("3.00")


def test_average_unit_price_rejects_zero_units():
    with pytest.raises(ZeroDivisionError):
        average_unit_price(Decimal("1.00"), 0)
