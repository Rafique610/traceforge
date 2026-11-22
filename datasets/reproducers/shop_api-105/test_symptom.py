"""Price rules: what a customer is charged for an order."""

from conftest import observe_price


def test_price_1(client, session):
    assert observe_price(client, session, [("18.75", 1), ("33.33", 1)], "Welcome10") == [200, '59.83']
