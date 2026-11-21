"""Checkout flow."""


def fetch_prices(cart):
    return [item["price"] * item["qty"] for item in cart]


def lookup_coupon(user, cart):
    return user.get("coupon")


def checkout(cart, user, settings):
    prices = fetch_prices(cart)
    discount = lookup_coupon(user, cart)
    total = sum(prices) - (discount or 0)
    reservation = settings["reserve"](cart)
    payment = settings["charge"](user, total)
    settings["send_receipt"](user, payment)
    return {"order": reservation["id"], "total": total}
