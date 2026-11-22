"""Reproducer: orders are accepted and queued, yet customers say some confirmations never arrive."""


def test_orders_are_accepted_and_queued(client, products, queue):
    for email in ("di@example.io", "second.di@example.io"):
        body = {"customer_email": email, "items": [{"product_id": products[1].id, "quantity": 2}]}
        assert client.post("/orders", json=body).status_code == 201
    assert len(queue.jobs) == 2
