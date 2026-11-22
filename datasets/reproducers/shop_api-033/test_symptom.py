"""Price rules: what a customer is charged for an order."""

from conftest import observe_price


def test_price_1(client, session):
    assert observe_price(client, session, [("7.45", 4), ("41.60", 3)]) == [200, '180.88']


def test_price_2(client, session):
    assert observe_price(client, session, [("33.33", 4)]) == [200, '155.98']
