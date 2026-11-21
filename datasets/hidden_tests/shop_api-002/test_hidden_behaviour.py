def test_upper_bound_is_inclusive(client, products):
    for qty in (99, 100):
        body = {"customer_email": "wholesale@shop.test", "items": [{"product_id": products[0].id, "quantity": qty}]}
        assert client.post("/orders", json=body).status_code == 201


def test_above_upper_bound_is_rejected(client, products):
    body = {"customer_email": "wholesale@shop.test", "items": [{"product_id": products[0].id, "quantity": 101}]}
    assert client.post("/orders", json=body).status_code == 422


def test_schema_accepts_100_units():
    from app.schemas import OrderItemIn

    assert OrderItemIn(product_id=3, quantity=100).quantity == 100
