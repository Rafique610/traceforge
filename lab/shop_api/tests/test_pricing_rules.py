"""Stock, coupons, shipping, tax and quotes: unit tests plus the quote/stock endpoints."""

from datetime import date
from decimal import Decimal

import pytest
from app import coupons, inventory, shipping
from app.models import Order, OrderItem, Product
from app.quote import quote
from app.settings import Settings

from app.settings import get_settings

D = Decimal
FAR = date(2099, 12, 31)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """Endpoints read Settings; credentials are required, pricing rules use their defaults."""
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def rules(**kw) -> Settings:
    return Settings(db_user="u", db_password="p", **kw)


def line(price: str, qty: int) -> OrderItem:
    return OrderItem(product_name="x", unit_price=D(price), quantity=qty)


def test_reserve_takes_units_and_refuses_shortfall():
    p = Product(id=1, name="Mug", price=D("7.25"), stock=5)
    inventory.reserve(p, 2)
    assert p.stock == 3
    with pytest.raises(inventory.OutOfStock):
        inventory.reserve(p, 4)
    assert p.stock == 3


def test_low_stock_lists_products_at_or_below_level():
    rows = [
        Product(id=1, name="a", price=D("1"), stock=9),
        Product(id=2, name="b", price=D("1"), stock=1),
        Product(id=3, name="c", price=D("1"), stock=4),
    ]
    assert [p.id for p in inventory.low_stock(rows, 4)] == [2, 3]


def test_coupon_codes_parse_case_insensitively():
    codes = coupons.parse_codes(" welcome10=10, ,BULK20=20")
    assert codes == {"WELCOME10": 10, "BULK20": 20}
    assert coupons.discount_pct("welcome10 ", codes, 30, FAR, date(2026, 1, 1)) == 10


def test_coupon_is_capped_and_unknown_or_expired_is_refused():
    codes = {"STAFF50": 50}
    assert coupons.discount_pct("STAFF50", codes, 30, FAR, date(2026, 1, 1)) == 30
    with pytest.raises(coupons.UnknownCoupon):
        coupons.discount_pct("NOPE", codes, 30, FAR, date(2026, 1, 1))
    with pytest.raises(coupons.ExpiredCoupon):
        coupons.discount_pct("STAFF50", codes, 30, date(2026, 1, 1), date(2026, 1, 2))


def test_discount_shipping_and_tax_amounts():
    assert coupons.apply_discount(D("80.00"), 25) == D("60.00")
    assert shipping.shipping_fee(D("49.99"), D("4.99"), D("50.00")) == D("4.99")
    assert shipping.shipping_fee(D("50.00"), D("4.99"), D("50.00")) == D("0.00")
    assert shipping.tax_amount(D("10.00"), D("0.17")) == D("1.70")


def test_quote_chains_the_rules_with_default_settings():
    q = quote([line("12.00", 2)], None, settings=rules())
    assert q == {
        "subtotal": D("24.00"), "discount_pct": 0, "goods": D("24.00"),
        "shipping": D("4.99"), "tax": D("4.08"), "grand_total": D("33.07"),
    }  # fmt: skip


def test_quote_with_coupon_and_free_shipping():
    q = quote([line("30.00", 2)], "bulk20", today=date(2026, 6, 1), settings=rules())
    assert (q["discount_pct"], q["goods"], q["shipping"]) == (20, D("48.00"), D("4.99"))
    q = quote([line("70.00", 1)], None, settings=rules())
    assert q["shipping"] == D("0.00") and q["grand_total"] == D("81.90")


def test_order_beyond_stock_is_409_and_saves_nothing(client, session, products):
    products[0].stock = 2
    session.commit()
    body = {"customer_email": "a@b.co", "items": [{"product_id": products[0].id, "quantity": 3}]}
    assert client.post("/orders", json=body).status_code == 409
    assert session.query(Order).count() == 0


def test_quote_endpoint_and_unknown_coupon(client, session):
    order = Order(customer_email="q@b.co", status="pending")
    order.items.append(OrderItem(product_id=1, product_name="Kettle", unit_price=D("42.00"), quantity=1))
    session.add(order)
    session.commit()
    body = client.get(f"/orders/{order.id}/quote").json()
    assert body["grand_total"] == "54.13" and body["shipping"] == "4.99"
    assert client.get(f"/orders/{order.id}/quote?coupon=NOPE").status_code == 404


def test_low_stock_endpoint(client, session, products):
    products[1].stock = 0
    session.commit()
    rows = client.get("/products/low-stock").json()
    assert [r["id"] for r in rows] == [products[1].id]
