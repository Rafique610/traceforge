"""Shelf stock: orders take units off the shelf; low shelves are reported."""

from conftest import observe_stock


def test_stock_1(client, session):
    assert observe_stock(client, session, 3, 3) == [201, 0, true]
