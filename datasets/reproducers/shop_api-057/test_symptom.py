"""Price rules: what a customer is charged for an order."""

from conftest import observe_price


def test_price_1(client, session):
    assert observe_price(client, session, [("7.45", 1)], "staff50") == [200, "11.10"]


def test_price_2(client, session):
    assert observe_price(client, session, [("12.00", 1), ("52.40", 3)], "staff50") == [200, "138.57"]
