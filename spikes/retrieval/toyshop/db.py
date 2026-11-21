"""A tiny fake connection pool and product table."""

from settings import settings

PRODUCTS = [
    {"sku": "A", "name": "Mug", "price": 5.0},
    {"sku": "B", "name": "Notebook", "price": 3.5},
]

_pool = None


def make_pool(size):
    if size <= 0:
        raise ValueError(f"pool size must be positive, got {size}")
    return [f"conn-{i}" for i in range(size)]


def get_pool():
    global _pool
    if _pool is None:
        _pool = make_pool(settings().db_pool_size)
    return _pool


def all_products():
    get_pool()
    return list(PRODUCTS)


def find_product(sku):
    for product in all_products():
        if product["sku"] == sku:
            return product
    return None
