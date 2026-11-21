"""Reproducer: order placement while the confirmation queue is unreachable."""

import pytest


def test_order_cannot_be_queued(real_queue_client, products):
    body = {"customer_email": "late@example.net", "items": [{"product_id": products[0].id, "quantity": 2}]}
    r = real_queue_client.post("/orders", json=body)
    assert r.status_code == 503
    assert "queue" in r.json()["detail"]
