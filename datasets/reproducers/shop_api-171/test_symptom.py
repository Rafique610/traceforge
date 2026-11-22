"""Reproducer: an order that has no lines still has a summary."""

from app.models import Order


def test_summary_of_an_order_without_lines(client, session):
    order = Order(customer_email="buyer@example.com", status="pending")
    session.add(order)
    session.commit()
    r = client.get(f"/orders/{order.id}/total")
    assert r.status_code == 200
    assert r.json()["headline"] is None
