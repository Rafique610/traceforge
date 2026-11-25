def round_money(x):
    return int(x * 100) / 100


def apply_pct(amount, pct):
    return round_money(amount * pct / 100)
