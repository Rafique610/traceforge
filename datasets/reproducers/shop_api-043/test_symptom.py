"""Price rules: what a customer is charged for an order."""

from conftest import observe_price


def test_price_1(client, session):
    assert observe_price(client, session, [("7.45", 1)], "Welcome10") == [200, '12.84']


def test_price_2(client, session):
    assert observe_price(client, session, [("24.10", 1), ("52.40", 2), ("33.33", 4)], "Welcome10") == [200, '276.12']
