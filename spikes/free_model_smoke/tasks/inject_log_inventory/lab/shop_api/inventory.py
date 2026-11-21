"""Stock reservation."""


class OutOfStock(Exception):
    pass


def reserve_stock(stock, sku, qty):
    """Reserve qty units of sku. Fails only when fewer than qty units are available."""
    available = stock.get(sku, 0)
    if qty >= available:
        raise OutOfStock(f"cannot reserve {qty} of sku {sku} (available {available})")
    stock[sku] = available - qty
    return stock[sku]
