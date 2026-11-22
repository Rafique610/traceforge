"""Reproducer: the average price per unit of an order."""

from decimal import Decimal

from app.models import Order, OrderItem


def test_average_price_of_a_single_line(client, session):
    order = Order(customer_email="buyer@example.com", status="pending")
    order.items.append(OrderItem(product_id=1, product_name="Pen", unit_price=Decimal("2.50"), quantity=4))
    session.add(order)
    session.commit()
    body = client.get(f"/orders/{order.id}/total").json()
    assert body["total"] == "10.00" and body["average_unit_price"] == "2.50"
