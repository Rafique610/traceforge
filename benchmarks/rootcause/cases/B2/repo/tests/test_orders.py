from app.inventory import Stock
from app.orders import create_order, quote


def test_quote():
    assert quote(50, 2, 10) == 108.0


def test_create_order():
    s = Stock()
    s.add("A", 10)
    assert create_order(s, "A", 100, 2, 10) == 216.0
    assert s.available("A") == 8


def test_create_order_exact_stock():
    s = Stock()
    s.add("B", 3)
    assert create_order(s, "B", 10, 3) == 36.0


def test_create_order_after_two_adds():
    s = Stock()
    s.add("C", 2)
    s.add("C", 3)
    assert create_order(s, "C", 10, 5) == 60.0
