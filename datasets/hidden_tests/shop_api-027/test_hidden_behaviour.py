"""Shelf stock: orders take units off the shelf; low shelves are reported."""

from conftest import observe_stock


def test_stock_1(client, session):
    assert observe_stock(client, session, 6, 7) == [409, 6, False]


def test_stock_2(client, session):
    assert observe_stock(client, session, 9, 2) == [201, 7, False]


def test_stock_3(client, session):
    assert observe_stock(client, session, 11, 6) == [201, 5, False]
