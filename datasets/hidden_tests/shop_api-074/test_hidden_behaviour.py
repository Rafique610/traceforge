"""Acceptance checks. Price rules: what a customer is charged for an order."""

from conftest import observe_price


def test_price_1(client, session):
    assert observe_price(client, session, [("15.50", 2), ("15.50", 5), ("6.15", 5)], "Staff50") == [200, '114.05']


def test_price_2(client, session):
    assert observe_price(client, session, [("50.00", 1)]) == [200, '58.50']


def test_price_3(client, session):
    assert observe_price(client, session, [("9.99", 1), ("15.50", 2), ("36.25", 2)], "Staff50") == [200, '92.94']
