# ruff: noqa: E501
"""Scenario-tested fault sites in shop_api (code faults and wrong settings defaults).

A site = one line in the lab that a real developer could get wrong, plus up to five realistic wrong
versions of it (`variants`). All variants of a site share one variant_group, so they always land in
the same split. Reproducer and hidden tests are found by `scenarios.discriminating` and use disjoint
inputs (D31). `distance` is a manual estimate: hops from the failing endpoint handler to the site.
"""

from traceforge.faultgen import lab_tree
from traceforge.faultgen.model import CaseDraft
from traceforge.faultgen.scenarios import discriminating
from traceforge.faultgen.templates.api_stub import api_conftest
from traceforge.faultgen.templates.scenario import HELPERS, render_tests

A = "lab/shop_api/app/"
QUOTE_PATH = {"quote": "public endpoint path /orders/{id}/quote"}

CODE_SITES = {
    "stock_check": dict(
        path=A + "inventory.py",
        qual="can_fulfil",
        family="boundary",
        distance=3,
        kind="stock",
        old="    return quantity <= product.stock\n",
        variants=[
            "    return quantity < product.stock\n",
            "    return quantity <= product.stock - 1\n",
            "    return quantity + 1 <= product.stock\n",
            "    return quantity < product.stock + 0\n",
        ],
    ),
    "stock_decrement": dict(
        path=A + "inventory.py",
        qual="reserve",
        family="wrong_state_update",
        distance=2,
        kind="stock",
        old="    product.stock -= quantity\n",
        variants=[
            "    product.stock -= 1\n",
            "    product.stock = quantity\n",
            "    product.stock -= quantity - 1\n",
            "    product.stock -= 2 * quantity\n",
        ],
    ),
    "low_stock_filter": dict(
        path=A + "inventory.py",
        qual="low_stock",
        family="boundary",
        distance=1,
        kind="stock",
        old="    return sorted((p for p in products if p.stock <= level), key=lambda p: (p.stock, p.id))\n",
        variants=[
            "    return sorted((p for p in products if p.stock < level), key=lambda p: (p.stock, p.id))\n",
            "    return sorted((p for p in products if p.stock <= level - 1), key=lambda p: (p.stock, p.id))\n",
            "    return sorted((p for p in products if p.stock >= level), key=lambda p: (p.stock, p.id))\n",
            "    return sorted((p for p in products if p.stock < level - 1), key=lambda p: (p.stock, p.id))\n",
        ],
    ),
    "code_table_case": dict(
        path=A + "coupons.py",
        qual="parse_codes",
        family="case_handling",
        distance=2,
        kind="price",
        old="        codes[code.strip().upper()] = int(pct)\n",
        variants=[
            "        codes[code.strip().lower()] = int(pct)\n",
            "        codes[code.strip().title()] = int(pct)\n",
            "        codes[code.strip()[:-1].upper()] = int(pct)\n",
            "        codes[code.strip().upper()] = int(pct) // 10\n",
        ],
    ),
    "discount_cap": dict(
        path=A + "coupons.py",
        qual="discount_pct",
        family="missing_cap",
        distance=2,
        kind="price",
        old="    return min(pct, cap)\n",
        variants=[
            "    return pct\n",
            "    return max(pct, cap)\n",
            "    return min(pct, cap - 10)\n",
            "    return min(pct, cap) * 2\n",
        ],
    ),
    "code_lookup": dict(
        path=A + "coupons.py",
        qual="discount_pct",
        family="case_handling",
        distance=2,
        kind="price",
        old="    pct = codes.get(code.strip().upper())\n",
        variants=[
            "    pct = codes.get(code)\n",
            "    pct = codes.get(code.upper())\n",
            "    pct = codes.get(code.strip())\n",
            "    pct = codes.get(code.strip().lower())\n",
        ],
    ),
    "discount_formula": dict(
        path=A + "coupons.py",
        qual="apply_discount",
        family="wrong_formula",
        distance=2,
        kind="price",
        old="    return money(amount * (100 - pct) / 100)\n",
        variants=[
            "    return money(amount * pct / 100)\n",
            "    return money(amount * (100 + pct) / 100)\n",
            "    return money(amount - pct)\n",
            "    return money(amount * (100 - pct) / 10)\n",
        ],
    ),
    "free_threshold": dict(
        path=A + "shipping.py",
        qual="shipping_fee",
        family="boundary",
        distance=2,
        kind="price",
        old="    return ZERO if amount >= free_over else money(fee)\n",
        variants=[
            "    return ZERO if amount > free_over else money(fee)\n",
            "    return ZERO if amount <= free_over else money(fee)\n",
            "    return money(fee)\n",
            "    return ZERO if amount >= free_over * 2 else money(fee)\n",
        ],
    ),
    "tax_formula": dict(
        path=A + "shipping.py",
        qual="tax_amount",
        family="wrong_formula",
        distance=2,
        kind="price",
        old="    return money(amount * rate)\n",
        variants=[
            "    return money(amount / rate)\n",
            "    return money(amount * rate * 10)\n",
            "    return money(rate)\n",
            "    return money(amount * (1 + rate))\n",
        ],
    ),
    "ship_base": dict(
        path=A + "quote.py",
        qual="quote",
        family="wrong_argument",
        distance=1,
        kind="price",
        allowed=QUOTE_PATH,
        old="    ship = shipping.shipping_fee(goods, s.shipping_fee, s.free_shipping_over)\n",
        variants=[
            "    ship = shipping.shipping_fee(subtotal, s.shipping_fee, s.free_shipping_over)\n",
            "    ship = shipping.shipping_fee(goods, s.free_shipping_over, s.shipping_fee)\n",
            "    ship = shipping.shipping_fee(goods + subtotal, s.shipping_fee, s.free_shipping_over)\n",
        ],
    ),
    "tax_base": dict(
        path=A + "quote.py",
        qual="quote",
        family="wrong_argument",
        distance=1,
        kind="price",
        allowed=QUOTE_PATH,
        old="    tax = shipping.tax_amount(goods, s.tax_rate)\n",
        variants=[
            "    tax = shipping.tax_amount(goods + ship, s.tax_rate)\n",
            "    tax = shipping.tax_amount(subtotal, s.tax_rate)\n",
            "    tax = shipping.tax_amount(ship, s.tax_rate)\n",
        ],
    ),
    "grand_sum": dict(
        path=A + "quote.py",
        qual="quote",
        family="missing_term",
        distance=1,
        kind="price",
        allowed=QUOTE_PATH,
        old='        "grand_total": money(goods + ship + tax),\n',
        variants=[
            '        "grand_total": money(goods + tax),\n',
            '        "grand_total": money(subtotal + ship + tax),\n',
            '        "grand_total": money(goods + ship),\n',
            '        "grand_total": money(goods + ship + tax + tax),\n',
        ],
    ),
    "rounding_mode": dict(
        path=A + "pricing.py",
        qual="money",
        family="rounding",
        distance=3,
        kind="total",
        old="    return value.quantize(CENT, rounding=ROUND_HALF_UP)\n",
        variants=[
            "    return value.quantize(CENT)\n",
            '    return value.quantize(CENT, rounding="ROUND_DOWN")\n',
            '    return value.quantize(CENT, rounding="ROUND_CEILING")\n',
            '    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)\n',
        ],
    ),
    "line_formula": dict(
        path=A + "pricing.py",
        qual="line_total",
        family="wrong_formula",
        distance=2,
        kind="total",
        old="    return money(unit_price * quantity)\n",
        variants=[
            "    return money(unit_price * (quantity - 1))\n",
            "    return money(unit_price + quantity)\n",
            "    return money(unit_price)\n",
            "    return money(unit_price * quantity * quantity)\n",
        ],
    ),
    "unit_aggregate": dict(
        path=A + "orders.py",
        qual="unit_count",
        family="wrong_aggregate",
        distance=1,
        kind="total",
        old="    return sum(item.quantity for item in items)\n",
        variants=[
            "    return len(items)\n",
            "    return sum(item.quantity for item in items[1:])\n",
            "    return max((item.quantity for item in items), default=0)\n",
            "    return sum(1 for item in items if item.quantity)\n",
        ],
    ),
    "total_loop": dict(
        path=A + "orders.py",
        qual="order_total",
        family="off_by_one",
        distance=1,
        kind="total",
        old="    for item in items:\n",
        variants=[
            "    for item in items[1:]:\n",
            "    for item in items[:-1]:\n",
            "    for item in items[:1]:\n",
        ],
    ),
}

S = A + "settings.py"
CONFIG_SITES = {
    "tax_rate": dict(
        kind="price",
        family="wrong_unit",
        line='    tax_rate: Decimal = Decimal("@@")\n',
        good="0.17",
        bad=["17", "0.71", "1.17", "0.017", "0,17"],
    ),
    "shipping_fee": dict(
        kind="price",
        family="wrong_value",
        line='    shipping_fee: Decimal = Decimal("@@")\n',
        good="4.99",
        bad=["49.9", "0.49", "9.49", "499", "4.99.0"],
    ),
    "free_shipping_over": dict(
        kind="price",
        family="wrong_value",
        line='    free_shipping_over: Decimal = Decimal("@@")\n',
        good="50.00",
        bad=["500.00", "5.00", "0.00", "-50.00", "5O.00"],
    ),
    "max_discount_pct": dict(
        kind="price",
        family="wrong_value",
        line="    max_discount_pct: int = @@\n",
        good="30",
        bad=["3", "300", "0", "15", "100"],
    ),
    "coupon_codes": dict(
        kind="price",
        family="malformed_value",
        line='    coupon_codes: str = "@@"\n',
        good="WELCOME10=10,BULK20=20,STAFF50=50",
        bad=[
            "WELCOME10=10,BULK2O=20,STAFF50=50",
            "WELCOME10=10;BULK20=20;STAFF50=50",
            "WELCOME10:10,BULK20:20,STAFF50:50",
            "WELCOME10=1,BULK20=2,STAFF50=5",
            "WELCOME10=10,BULK20=20,STAFF50=five",
        ],
    ),
    "coupons_valid_until": dict(
        kind="price",
        family="invalid_date",
        line='    coupons_valid_until: str = "@@"\n',
        good="2099-12-31",
        bad=["2020-12-31", "31/12/2099", "2099-31-12", "2099-12-32", "Dec 31 2099"],
    ),
    "low_stock_level": dict(
        kind="stock",
        family="wrong_value",
        line="    low_stock_level: int = @@\n",
        good="3",
        bad=["0", "30", "-1", "1", "10"],
    ),
}

DOC = {
    "price": "Price rules: what a customer is charged for an order.",
    "total": "Order totals and counts as shown on the order summary.",
    "stock": "Shelf stock: orders take units off the shelf; low shelves are reported.",
}


def _draft(
    case_id,
    cls,
    family,
    group,
    kind,
    path,
    new_text,
    qual,
    distance,
    log_format,
    params,
    lab,
    gold_keys=(),
    allowed=None,
    notes="",
) -> CaseDraft | None:
    patch = _patch(lab, path, new_text)
    vis, vis_exp = discriminating(lab, patch, kind, hidden=False, want=2)
    hid, hid_exp = discriminating(lab, patch, kind, hidden=True, want=3)
    if not vis or not hid:
        return None  # this wrong version is not observable through the endpoint: drop it
    return CaseDraft(
        case_id=case_id, cause_class=cls, fault_family=family, service="shop_api", variant_group=group,
        log_format=log_format, distance=distance, template=f"sites.{kind}", params=params,
        edits={path: new_text}, gold_config_keys=list(gold_keys), gold_symbols=[(path, qual)],
        reproducer_files={"conftest.py": api_conftest() + HELPERS, "test_symptom.py": render_tests(kind, vis, vis_exp, DOC[kind])},
        hidden_files={"conftest.py": api_conftest(("Lid", "1.15"), ("Jar", "6.35")) + HELPERS,
                      "test_hidden_behaviour.py": render_tests(kind, hid, hid_exp, DOC[kind])},
        allowed_terms=allowed or {}, notes=notes or "distance: manual estimate (hops from endpoint handler to site)",
    )  # fmt: skip


def _patch(lab, path: str, new_text: str) -> str:
    from traceforge.faultgen.patching import make_patch

    return make_patch({path: (lab_tree.read_lf(lab.parent / path), new_text)})


def code_variants(site: str, lab) -> list[tuple[dict, str]]:
    s = CODE_SITES[site]
    text = lab_tree.read_lf(lab.parent / s["path"])
    if text.count(s["old"]) != 1:
        raise ValueError(f"{s['path']}: expected exactly one line {s['old']!r}")
    return [
        ({"site": site, "variant": i}, text.replace(s["old"], v))
        for i, v in enumerate(s["variants"])
    ]


def make_code(case_id: str, site: str, variant: int, lab, log_format: str) -> CaseDraft | None:
    s = CODE_SITES[site]
    params, new_text = code_variants(site, lab)[variant]
    return _draft(
        case_id,
        "application_code",
        s["family"],
        f"code:{site}",
        s["kind"],
        s["path"],
        new_text,
        s["qual"],
        s["distance"],
        log_format,
        params,
        lab,
        allowed=s.get("allowed"),
    )


def make_config(case_id: str, field: str, variant: int, lab, log_format: str) -> CaseDraft | None:
    c = CONFIG_SITES[field]
    text = lab_tree.read_lf(lab.parent / S)
    old = c["line"].replace("@@", c["good"])
    if text.count(old) != 1:
        raise ValueError(f"{S}: expected exactly one line {old!r}")
    bad = c["bad"][variant]
    return _draft(
        case_id,
        "configuration",
        c["family"],
        f"settings_default:shop_api:{field}",
        c["kind"],
        S,
        text.replace(old, c["line"].replace("@@", bad)),
        f"Settings.{field}",
        1,
        log_format,
        {"field": field, "bad_value": bad},
        lab,
        gold_keys=[f"shop_api.{field.upper()}"],
        notes="distance 1 (manual): the handler/quote reads the field; the wrong value is its default",
    )
