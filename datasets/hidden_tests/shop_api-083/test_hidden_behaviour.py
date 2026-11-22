"""Acceptance checks. Price rules: what a customer is charged for an order."""

from conftest import observe_price


def test_price_1(client, session):
    assert observe_price(client, session, [("50.00", 6), ("2.85", 2)], "Staff50") == [200, '250.37']


def test_price_2(client, session):
    assert observe_price(client, session, [], "welcome10 ") == [200, '4.99']


def test_price_3(client, session):
    assert observe_price(client, session, [("50.00", 2), ("6.15", 5), ("64.80", 2)], "Staff50") == [200, '213.23']
