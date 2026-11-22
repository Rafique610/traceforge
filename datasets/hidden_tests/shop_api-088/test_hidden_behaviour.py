"""Price rules: what a customer is charged for an order."""

from conftest import observe_price


def test_price_1(client, session):
    assert observe_price(client, session, [("27.90", 2)], "BULK20") == [200, "57.22"]


def test_price_2(client, session):
    assert observe_price(client, session, [("21.05", 1), ("2.85", 1), ("9.99", 2)], "welcome10 ") == [200, "51.19"]


def test_price_3(client, session):
    assert observe_price(client, session, [("2.85", 6), ("21.05", 1)]) == [200, "49.63"]
