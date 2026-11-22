"""Acceptance checks. Price rules: what a customer is charged for an order."""

from conftest import observe_price


def test_price_1(client, session):
    assert observe_price(client, session, [("64.80", 6)], "welcome10 ") == [200, '409.41']


def test_price_2(client, session):
    assert observe_price(client, session, [("21.05", 1), ("2.85", 1), ("9.99", 2)], "welcome10 ") == [200, '51.19']


def test_price_3(client, session):
    assert observe_price(client, session, [("9.99", 5), ("27.90", 1)], "welcome10 ") == [200, '81.98']
