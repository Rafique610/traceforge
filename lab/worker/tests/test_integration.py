"""Needs the running lab stack: order created via the API is confirmed by the worker within 10 s."""

import time

import httpx
import pytest

pytestmark = pytest.mark.integration


def test_worker_confirms_order_within_10s(lab_url):
    products = httpx.get(f"{lab_url}/products", timeout=5).json()
    assert products, "run the seed first (task lab:reset)"
    body = {
        "customer_email": "it@example.com",
        "items": [{"product_id": products[0]["id"], "quantity": 1}],
    }
    oid = httpx.post(f"{lab_url}/orders", json=body, timeout=5).json()["id"]
    deadline = time.time() + 10
    status = "pending"
    while time.time() < deadline and status != "confirmed":
        time.sleep(0.5)
        status = httpx.get(f"{lab_url}/orders/{oid}", timeout=5).json()["status"]
    assert status == "confirmed"
