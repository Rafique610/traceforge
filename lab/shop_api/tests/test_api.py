"""Visible endpoint tests against in-memory SQLite and a fake queue (no Docker)."""

from decimal import Decimal

from app.models import Order


def test_empty_catalogue_returns_empty_list(client):
    r = client.get("/products")
    assert r.status_code == 200 and r.json() == []


def test_list_and_get_product(client, products):
    assert [p["name"] for p in client.get("/products").json()] == ["Mug", "Beans"]
    assert client.get(f"/products/{products[0].id}").json()["price"] == "7.25"


def test_missing_product_is_404(client):
    assert client.get("/products/999").status_code == 404


def test_create_order_enqueues_job_and_reports_total(client, products, queue):
    body = {
        "customer_email": "a@b.co",
        "items": [{"product_id": products[0].id, "quantity": 2}],
    }
    r = client.post("/orders", json=body)
    assert r.status_code == 201
    assert r.json()["status"] == "pending" and r.json()["total"] == "14.50"
    assert queue.jobs == [(r.json()["id"], Decimal("14.50"))]


def test_create_order_validates_input(client, products):
    for qty in (0, -1):
        body = {
            "customer_email": "a@b.co",
            "items": [{"product_id": products[0].id, "quantity": qty}],
        }
        assert client.post("/orders", json=body).status_code == 422
    assert (
        client.post(
            "/orders", json={"customer_email": "a@b.co", "items": []}
        ).status_code
        == 422
    )
    assert (
        client.post("/orders", json={"customer_email": "nope", "items": []}).status_code
        == 422
    )


def test_create_order_unknown_product_is_404(client):
    body = {"customer_email": "a@b.co", "items": [{"product_id": 42, "quantity": 1}]}
    assert client.post("/orders", json=body).status_code == 404


def test_queue_down_returns_503_and_keeps_pending_order(
    client, products, queue, session
):
    queue.fail = True
    body = {
        "customer_email": "a@b.co",
        "items": [{"product_id": products[0].id, "quantity": 1}],
    }
    assert client.post("/orders", json=body).status_code == 503
    assert session.get(Order, 1).status == "pending"


def test_order_total_endpoint(client, products):
    body = {
        "customer_email": "a@b.co",
        "items": [
            {"product_id": products[0].id, "quantity": 2},
            {"product_id": products[1].id, "quantity": 1},
        ],
    }
    oid = client.post("/orders", json=body).json()["id"]
    t = client.get(f"/orders/{oid}/total").json()
    assert t["total"] == "33.00" and t["item_count"] == 3
    assert t["average_unit_price"] == "11.00" and t["headline"] == "Mug"
    assert client.get("/orders/999/total").status_code == 404


def test_order_without_lines_totals_zero(client, session):
    session.add(Order(customer_email="a@b.co", status="pending"))
    session.commit()
    t = client.get("/orders/1/total").json()
    assert (
        t["total"] == "0.00"
        and t["average_unit_price"] == "0.00"
        and t["headline"] is None
    )


def test_health_reports_redis_down(client, queue):
    assert client.get("/health").status_code == 200
    queue.fail = True
    r = client.get("/health")
    assert r.status_code == 503 and r.json()["redis"].startswith("down")


def test_health_live_always_ok(client, queue):
    queue.fail = True
    assert client.get("/health/live").json() == {"status": "ok"}


def test_queue_failure_is_logged_with_traceback(client, products, queue, caplog):
    queue.fail = True
    body = {
        "customer_email": "a@b.co",
        "items": [{"product_id": products[0].id, "quantity": 1}],
    }
    assert client.post("/orders", json=body).status_code == 503
    rec = next(r for r in caplog.records if r.name == "app.orders")
    assert rec.levelname == "ERROR" and "enqueue failed" in rec.getMessage()
    assert rec.exc_info and rec.exc_info[0] is ConnectionError


def test_validation_failure_is_logged_and_keeps_422_body(client, products, caplog):
    body = {
        "customer_email": "a@b.co",
        "items": [{"product_id": products[0].id, "quantity": 100 + 1}],
    }
    r = client.post("/orders", json=body)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "items", 0, "quantity"]
    msgs = [x.getMessage() for x in caplog.records if x.name == "app.main"]
    expected = (
        "validation error on POST /orders: items.0.quantity: "
        "Input should be less than or equal to 100"
    )
    assert msgs == [expected]
    assert "a@b.co" not in msgs[0]
