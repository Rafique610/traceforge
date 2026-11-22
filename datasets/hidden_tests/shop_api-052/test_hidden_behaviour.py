from decimal import Decimal

from app.pricing import average_unit_price


def test_average_over_several_units():
    assert average_unit_price(Decimal("9.00"), 3) == Decimal("3.00")
    assert average_unit_price(Decimal("31.00"), 5) == Decimal("6.20")


def test_single_unit_average_is_the_total():
    assert average_unit_price(Decimal("7.77"), 1) == Decimal("7.77")
