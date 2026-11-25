from app import settings
from app.money import apply_pct, round_money


def net_price(price, qty):
    return round_money(price + qty)


def discount(amount, pct):
    return round_money(amount - apply_pct(amount, pct))


def tax(amount):
    return round_money(amount * settings.TAX_RATE)


def gross(price, qty, pct=0):
    net = discount(net_price(price, qty), pct)
    return round_money(net + tax(net))
