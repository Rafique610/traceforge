"""Order totals and checkout."""

import pricing


def order_total(items):
    if not items:
        return 0.0
    currency = items[0].currency
    subtotal = sum(pricing.line_total(item.price, item.qty) for item in items)
    return {"currency": currency, "amount": pricing.add_tax(subtotal)}


def checkout(items, discount=0.0):
    total = order_total(items)
    if not total:
        return {"status": "empty"}
    total["amount"] = pricing.apply_discount(total["amount"], discount)
    return {"status": "ok", "total": total}
