"""Needs the running lab stack: `task lab:up`, then `pytest lab -m integration`."""

import httpx
import pytest

pytestmark = pytest.mark.integration


def test_api_health_and_products(lab_url):
    assert httpx.get(f"{lab_url}/health", timeout=5).json()["status"] == "ok"
    assert httpx.get(f"{lab_url}/products", timeout=5).status_code == 200


def test_create_order_roundtrip(lab_url):
    products = httpx.get(f"{lab_url}/products", timeout=5).json()
    assert products, "run the seed first (task lab:reset)"
    body = {
        "customer_email": "it@example.com",
        "items": [{"product_id": products[0]["id"], "quantity": 2}],
    }
    r = httpx.post(f"{lab_url}/orders", json=body, timeout=5)
    assert r.status_code == 201
    total = httpx.get(f"{lab_url}/orders/{r.json()['id']}/total", timeout=5).json()
    assert total["item_count"] == 2
