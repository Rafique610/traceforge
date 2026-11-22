"""Stock levels: reserve units when an order is placed, report products running low."""

from app.models import Product


class OutOfStock(Exception):
    def __init__(self, product_id: int, wanted: int, left: int):
        super().__init__(f"product {product_id}: wanted {wanted}, {left} left")
        self.product_id = product_id
        self.wanted = wanted
        self.left = left


def can_fulfil(product: Product, quantity: int) -> bool:
    """True when the shelf holds at least `quantity` units."""
    return quantity <= product.stock


def reserve(product: Product, quantity: int) -> None:
    """Take units off the shelf. Raises OutOfStock and leaves stock untouched if short."""
    if not can_fulfil(product, quantity):
        raise OutOfStock(product.id, quantity, product.stock)
    product.stock -= quantity


def low_stock(products: list[Product], level: int) -> list[Product]:
    """Products at or below the reorder level, fewest units first."""
    return sorted((p for p in products if p.stock <= level), key=lambda p: (p.stock, p.id))
