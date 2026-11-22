from decimal import Decimal

from app.models import Order, OrderItem
from app.orders import order_headline


def test_headline_of_no_lines_and_of_several():
    assert order_headline([]) is None
    lines = [
        OrderItem(product_name="Tea", unit_price=Decimal("4.20"), quantity=1),
        OrderItem(product_name="Jam", unit_price=Decimal("2.00"), quantity=2),
    ]
    assert order_headline(lines) == "Tea"


def test_empty_orders_over_http(client, session):
    for email in ("walkin@shop.test", "phone@shop.test"):
        order = Order(customer_email=email, status="pending")
        session.add(order)
        session.commit()
        body = client.get(f"/orders/{order.id}/total").json()
        assert body["headline"] is None and body["item_count"] == 0
