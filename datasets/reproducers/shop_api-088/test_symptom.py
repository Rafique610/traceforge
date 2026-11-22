"""Price rules: what a customer is charged for an order."""

from conftest import observe_price


def test_price_1(client, session):
    assert observe_price(client, session, [("24.10", 2)], "bulk20") == [200, "50.11"]


def test_price_2(client, session):
    assert observe_price(client, session, [("33.33", 1)], "staff50") == [200, "32.29"]
