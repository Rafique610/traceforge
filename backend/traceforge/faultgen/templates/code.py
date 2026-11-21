# ruff: noqa: E501
"""Application-code faults: one guard / boundary / divisor changed in the shop API.

`SITES` holds the parameterised mutation sites. Each site: file, exact old line, new line, gold qualname,
family, manual distance, plus the visible reproducer and hidden tests (different inputs, D31).
Visible = what the agent sees; hidden = never mounted into the worktree.
"""

from traceforge.faultgen import lab_tree
from traceforge.faultgen.model import CaseDraft
from traceforge.faultgen.templates.api_stub import api_conftest

ORDER_BODY = '{"customer_email": "@@EMAIL@@", "items": [{"product_id": products[0].id, "quantity": @@QTY@@}]}'

# --- site: quantity upper bound (boundary) -------------------------------------------------------
QTY_REPRO = f'''"""Reproducer: the contract accepts quantities 1..100 per line."""


def test_maximum_quantity_is_accepted(client, products, queue):
    body = {ORDER_BODY.replace("@@EMAIL@@", "bulk@example.org").replace("@@QTY@@", "100")}
    r = client.post("/orders", json=body)
    assert r.status_code == 201, r.text
    assert len(queue.jobs) == 1
'''
QTY_HIDDEN = f"""def test_upper_bound_is_inclusive(client, products):
    for qty in (99, 100):
        body = {ORDER_BODY.replace("@@EMAIL@@", "wholesale@shop.test").replace("@@QTY@@", "qty")}
        assert client.post("/orders", json=body).status_code == 201


def test_above_upper_bound_is_rejected(client, products):
    body = {ORDER_BODY.replace("@@EMAIL@@", "wholesale@shop.test").replace("@@QTY@@", "101")}
    assert client.post("/orders", json=body).status_code == 422


def test_schema_accepts_100_units():
    from app.schemas import OrderItemIn

    assert OrderItemIn(product_id=3, quantity=100).quantity == 100
"""

# --- site: empty order headline (missing guard) ----------------------------------------------------
HEAD_REPRO = '''"""Reproducer: an order that has no lines still has a summary."""

from app.models import Order


def test_summary_of_an_order_without_lines(client, session):
    order = Order(customer_email="buyer@example.com", status="pending")
    session.add(order)
    session.commit()
    r = client.get(f"/orders/{order.id}/total")
    assert r.status_code == 200
    assert r.json()["headline"] is None
'''
HEAD_HIDDEN = """from decimal import Decimal

from app.models import Order, OrderItem
from app.orders import order_headline


def test_headline_of_no_lines_and_of_several():
    assert order_headline([]) is None
    lines = [
        OrderItem(product_name="Tea", unit_price=Decimal("4.20"), quantity=1),
        OrderItem(product_name="Jam", unit_price=Decimal("2.00"), quantity=2),
    ]
    assert order_headline(lines) == "Tea"


def test_empty_orders_over_http(client, session):
    for email in ("walkin@shop.test", "phone@shop.test"):
        order = Order(customer_email=email, status="pending")
        session.add(order)
        session.commit()
        body = client.get(f"/orders/{order.id}/total").json()
        assert body["headline"] is None and body["item_count"] == 0
"""

# --- site: average price divisor (off by one) ------------------------------------------------------
AVG_REPRO = '''"""Reproducer: the average price per unit of an order."""

from decimal import Decimal

from app.models import Order, OrderItem


def test_average_price_of_a_single_line(client, session):
    order = Order(customer_email="buyer@example.com", status="pending")
    order.items.append(OrderItem(product_id=1, product_name="Pen", unit_price=Decimal("2.50"), quantity=4))
    session.add(order)
    session.commit()
    body = client.get(f"/orders/{order.id}/total").json()
    assert body["total"] == "10.00" and body["average_unit_price"] == "2.50"
'''
AVG_HIDDEN = """from decimal import Decimal

from app.pricing import average_unit_price


def test_average_over_several_units():
    assert average_unit_price(Decimal("9.00"), 3) == Decimal("3.00")
    assert average_unit_price(Decimal("31.00"), 5) == Decimal("6.20")


def test_single_unit_average_is_the_total():
    assert average_unit_price(Decimal("7.77"), 1) == Decimal("7.77")
"""

SITES = {
    "quantity_upper_bound": dict(
        path="lab/shop_api/app/schemas.py",
        qual="OrderItemIn.quantity",
        family="boundary",
        distance=1,
        old="    quantity: int = Field(gt=0, le=100)\n",
        new="    quantity: int = Field(gt=0, lt=100)\n",
        repro=QTY_REPRO,
        hidden=QTY_HIDDEN,
        products=(("Cup", "4.10"), ("Tin", "9.90")),
        hproducts=(("Lid", "1.15"), ("Jar", "6.35")),
        log_format="uvicorn_access",
        allowed_shared={"100": "contract boundary value: the fault is exactly at quantity 100"},
    ),
    "empty_order_headline": dict(
        path="lab/shop_api/app/orders.py",
        qual="order_headline",
        family="missing_guard",
        distance=1,
        old="    return items[0].product_name if items else None\n",
        new="    return items[0].product_name\n",
        repro=HEAD_REPRO,
        hidden=HEAD_HIDDEN,
        products=(("Cup", "4.10"), ("Tin", "9.90")),
        hproducts=(("Lid", "1.15"), ("Jar", "6.35")),
        log_format="uvicorn_access",
    ),
    "average_divisor": dict(
        path="lab/shop_api/app/pricing.py",
        qual="average_unit_price",
        family="off_by_one",
        distance=2,
        old="    return money(total / quantity)\n",
        new="    return money(total / (quantity - 1))\n",
        repro=AVG_REPRO,
        hidden=AVG_HIDDEN,
        products=(("Cup", "4.10"), ("Tin", "9.90")),
        hproducts=(("Lid", "1.15"), ("Jar", "6.35")),
        log_format="uvicorn_access",
        allowed_terms={
            "average_unit_price": "public response field (CONTRACT.md) the symptom is read from"
        },
    ),
}


def make(
    case_id: str, site: str = "quantity_upper_bound", service: str = "shop_api", lab=None
) -> CaseDraft:
    lab = lab or lab_tree.repo_root() / "lab"
    s = SITES[site]
    text = lab_tree.read_lf(lab.parent / s["path"])
    if text.count(s["old"]) != 1:
        raise ValueError(f"{s['path']}: expected exactly one line {s['old']!r}")
    return CaseDraft(
        case_id=case_id,
        cause_class="application_code",
        fault_family=s["family"],
        service=service,
        variant_group=f"code:{site}",
        log_format=s["log_format"],
        distance=s["distance"],
        template=f"code.{site}",
        params={"site": site},
        edits={s["path"]: text.replace(s["old"], s["new"])},
        gold_symbols=[(s["path"], s["qual"])],
        reproducer_files={
            "conftest.py": api_conftest(*s["products"]),
            "test_symptom.py": s["repro"],
        },
        hidden_files={
            "conftest.py": api_conftest(*s["hproducts"]),
            "test_hidden_behaviour.py": s["hidden"],
        },
        allowed_shared=s.get("allowed_shared", {}),
        allowed_terms=s.get("allowed_terms", {}),
        notes="distance is a manual estimate (hops from the failing endpoint to the mutated site)",
    )
