"""Request handlers (called directly by the spike's reproducers)."""

import cart
import db
import orders
import pricing
import queue_client


def checkout_handler(body):
    items = cart.load_items(body)
    result = orders.checkout(items, body.get("discount", 0.0))
    if result["status"] == "ok":
        queue_client.send_order_email(body.get("order_id", 0))
    return result


def price_quote(body):
    return {"unit": pricing.unit_price(body["total"], body["qty"])}


def list_products():
    return db.all_products()


def resend_email(body):
    return queue_client.send_order_email(body["order_id"])
