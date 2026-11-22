"""Price rules: what a customer is charged for an order."""

from conftest import observe_price


def test_price_1(client, session):
    assert observe_price(client, session, [("7.45", 3), ("41.60", 1)]) == [200, '74.82']


def test_price_2(client, session):
    assert observe_price(client, session, [("3.20", 2), ("24.10", 3), ("3.20", 3)], "bulk20") == [200, '82.65']
