from app.convert import convert


def total_usd(accounts):
    return round(sum(convert(a.balance, a.currency, "USD") for a in accounts), 2)
