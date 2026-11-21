"""Invoice building."""
from tax import compute_tax


class InvoiceMismatch(Exception):
    pass


def build_invoice(items, region, expected_total=None):
    subtotal = round(sum(price * qty for price, qty in items), 2)
    tax = compute_tax(subtotal, region)
    total = round(subtotal + tax, 2)
    if expected_total is not None and abs(total - expected_total) > 0.005:
        raise InvoiceMismatch(f"invoice total {total} != payment total {expected_total}")
    return {"subtotal": subtotal, "tax": tax, "total": total}
