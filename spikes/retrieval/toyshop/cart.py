"""Turn a raw request body into cart line items."""

from dataclasses import dataclass


@dataclass
class LineItem:
    sku: str
    price: float
    qty: int
    currency: str = "PKR"


def parse_qty(raw):
    return int(raw)


def parse_price(raw):
    return float(raw)


def load_items(body):
    items = []
    for row in body.get("items", []):
        items.append(LineItem(sku=row["sku"], price=parse_price(row["price"]), qty=parse_qty(row["qty"])))
    return items
