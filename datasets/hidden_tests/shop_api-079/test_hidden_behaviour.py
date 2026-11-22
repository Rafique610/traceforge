"""Price rules: what a customer is charged for an order."""

from conftest import observe_price


def test_price_1(client, session):
    assert observe_price(client, session, [], "welcome10 ") == [200, '4.99']


def test_price_2(client, session):
    assert observe_price(client, session, [("36.25", 5)], "BULK20") == [200, '169.65']


def test_price_3(client, session):
    assert observe_price(client, session, [("27.90", 2)], "BULK20") == [200, '57.22']
