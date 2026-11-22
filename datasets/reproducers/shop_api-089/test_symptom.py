"""Shelf stock: orders take units off the shelf; low shelves are reported."""

from conftest import observe_stock


def test_stock_1(client, session):
    assert observe_stock(client, session, 10, 1) == [201, 9, False]


def test_stock_2(client, session):
    assert observe_stock(client, session, 12, 4) == [201, 8, False]
