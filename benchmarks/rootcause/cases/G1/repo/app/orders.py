from app import cache
from app.pricing import gross
from app.validate import parse_qty


def quote(price, qty, pct=0):
    return gross(price, qty, pct)


def create_order(stock, sku, price, qty, pct=0):
    stock.reserve(sku, qty)
    total = gross(price, qty, pct)
    cache.connect().set(f"order:{sku}", total)
    return total


def create_order_from_text(stock, sku, price, qty_text):
    return create_order(stock, sku, price, parse_qty(qty_text))
