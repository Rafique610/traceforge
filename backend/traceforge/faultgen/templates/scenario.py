# ruff: noqa: E501
"""Scenario tests: shared test helpers, a probe script, and rendering of one test per scenario.

A scenario is a small, concrete use of a public endpoint. Three kinds:
- price:  {"items": [[price, qty], ...], "coupon": str | None}  -> GET /orders/{id}/quote
- total:  {"items": [[price, qty], ...]}                         -> GET /orders/{id}/total
- stock:  {"stock": int, "qty": int}                             -> POST /orders, then GET /products/low-stock

The same helper source runs in the probe (to observe the original and the faulty tree) and in the
generated reproducer/hidden tests, so expected values are exactly what the correct code returns.
Inputs live in call arguments; expected values live only inside `assert` (D31 overlap check).
"""

import json

HELPERS = """
import pytest
from decimal import Decimal

from app.models import Order, OrderItem, Product
from app.settings import get_settings


@pytest.fixture(autouse=True)
def _service_env(monkeypatch):
    monkeypatch.setenv("DB_USER", "shopper")
    monkeypatch.setenv("DB_PASSWORD", "unused")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _order(session, items):
    order = Order(customer_email="buyer@example.com", status="pending")
    for n, (price, qty) in enumerate(items, 1):
        order.items.append(OrderItem(product_id=n, product_name=f"Item {n}", unit_price=Decimal(price), quantity=qty))
    session.add(order)
    session.commit()
    return order


def observe_price(client, session, items, coupon=None):
    order = _order(session, items)
    url = f"/orders/{order.id}/quote" + (f"?coupon={coupon}" if coupon else "")
    r = client.get(url)
    return [r.status_code, r.json().get("grand_total") if r.status_code == 200 else None]


def observe_total(client, session, items):
    r = client.get(f"/orders/{_order(session, items).id}/total")
    b = r.json()
    return [r.status_code, b.get("total"), b.get("item_count"), b.get("average_unit_price"), b.get("headline")]


def observe_stock(client, session, stock, qty):
    p = Product(name="Shelf item", price=Decimal("2.00"), stock=stock)
    session.add(p)
    session.commit()
    body = {"customer_email": "buyer@example.com", "items": [{"product_id": p.id, "quantity": qty}]}
    status = client.post("/orders", json=body).status_code
    session.refresh(p)
    low = [row["id"] for row in client.get("/products/low-stock").json()]
    return [status, p.stock, p.id in low]
"""

TEST_HEAD = '''"""@@DOC@@"""

from conftest import observe_@@KIND@@
'''

TEST_ONE = """

def test_@@KIND@@_@@N@@(client, session):
    assert observe_@@KIND@@(client, session, @@ARGS@@) == @@EXPECTED@@
"""


def args_of(kind: str, sc: dict) -> str:
    if kind == "stock":
        return f"{sc['stock']}, {sc['qty']}"
    items = "[" + ", ".join(f'("{p}", {q})' for p, q in sc["items"]) + "]"
    if kind == "price" and sc.get("coupon"):
        return f'{items}, "{sc["coupon"]}"'
    return items


def render_tests(kind: str, scenarios: list[dict], expected: list, doc: str) -> str:
    out = TEST_HEAD.replace("@@DOC@@", doc).replace("@@KIND@@", kind)
    for n, (sc, exp) in enumerate(zip(scenarios, expected, strict=True), 1):
        out += (
            TEST_ONE.replace("@@KIND@@", kind)
            .replace("@@N@@", str(n))
            .replace("@@ARGS@@", args_of(kind, sc))
            .replace("@@EXPECTED@@", json.dumps(exp))
        )
    return out


PROBE = """
import json, sys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import get_session
from app.main import app
from app.models import Base
from app.queue import get_queue

class Q:
    def enqueue_confirmation(self, order_id, total): return "job"
    def ping(self): return True
    def worker_alive(self): return True

kind, scenarios = json.load(sys.stdin)
out = []
for sc in scenarios:
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    def _s():
        with Session(eng, expire_on_commit=False) as s:
            yield s
    app.dependency_overrides[get_session] = _s
    app.dependency_overrides[get_queue] = lambda: Q()
    client = TestClient(app, raise_server_exceptions=False)
    with Session(eng, expire_on_commit=False) as session:
        try:
            if kind == "stock":
                obs = observe_stock(client, session, sc["stock"], sc["qty"])
            elif kind == "total":
                obs = observe_total(client, session, sc["items"])
            else:
                obs = observe_price(client, session, sc["items"], sc.get("coupon"))
        except Exception as e:
            obs = ["error", type(e).__name__]
    out.append(obs)
print(json.dumps(out))
"""
