"""Sales tax."""

TAX_RATES = {"CA": 7.25, "NY": 8.0, "TX": 6.25}


def compute_tax(subtotal, region):
    """Sales tax in dollars for a subtotal; rates are percentages."""
    rate = TAX_RATES.get(region, 0.0)
    return subtotal * rate // 100
