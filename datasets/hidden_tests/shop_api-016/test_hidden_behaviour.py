"""Shelf stock: orders take units off the shelf; low shelves are reported."""

from conftest import observe_stock


def test_stock_1(client, session):
    assert observe_stock(client, session, 6, 6) == [201, 0, true]


def test_stock_2(client, session):
    assert observe_stock(client, session, 7, 5) == [201, 2, true]


def test_stock_3(client, session):
    assert observe_stock(client, session, 8, 5) == [201, 3, true]
