"""Reproducer: the contract accepts quantities 1..100 per line."""


def test_maximum_quantity_is_accepted(client, products, queue):
    body = {"customer_email": "bulk@example.org", "items": [{"product_id": products[0].id, "quantity": 100}]}
    r = client.post("/orders", json=body)
    assert r.status_code == 201, r.text
    assert len(queue.jobs) == 1
