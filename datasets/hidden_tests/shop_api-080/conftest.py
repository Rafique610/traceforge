"""Test plumbing: in-memory SQLite and a recording queue (test doubles)."""

from decimal import Decimal

import pytest
from app.db import get_session
from app.main import app
from app.models import Base, Product
from app.queue import get_queue
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


class RecordingQueue:
    def __init__(self):
        self.jobs = []
        self.alive = True

    def enqueue_confirmation(self, order_id, total):
        self.jobs.append((order_id, total))
        return "job"

    def ping(self):
        return True

    def worker_alive(self):
        return self.alive


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine, expire_on_commit=False) as s:
        yield s


@pytest.fixture
def products(session):
    rows = [Product(name="Lid", price=Decimal("1.15")), Product(name="Jar", price=Decimal("6.35"))]
    session.add_all(rows)
    session.commit()
    return rows


@pytest.fixture
def queue():
    return RecordingQueue()


@pytest.fixture
def client(engine, queue):
    def _session():
        with Session(engine, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_queue] = lambda: queue
    yield TestClient(app)
    app.dependency_overrides.clear()

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
