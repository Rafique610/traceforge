"""Reproducer: some orders are refused with 503 and the same order succeeds when retried."""


def test_retry_of_a_refused_order_succeeds(flaky_client, products):
    body = {"customer_email": "bo@example.net", "items": [{"product_id": products[0].id, "quantity": 1}]}
    codes = [flaky_client.post("/orders", json=body).status_code for _ in range(4)]
    assert 503 in codes and codes[-1] == 201
