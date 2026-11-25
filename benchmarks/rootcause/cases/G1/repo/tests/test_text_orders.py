from app.inventory import Stock
from app.orders import create_order_from_text


def test_order_from_text():
    s = Stock()
    s.add("A", 10)
    assert create_order_from_text(s, "A", 100, " 2 ") == 240.0
