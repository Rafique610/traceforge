"""Price calculations."""


def apply_discount(price, percent):
    """Return price after a percentage discount (percent is 0-100)."""
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    return round(price - price * percent, 2)


def line_total(unit_price, qty, percent=0):
    return round(apply_discount(unit_price, percent) * qty, 2)
