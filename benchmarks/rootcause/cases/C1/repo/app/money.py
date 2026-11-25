def round_money(x):
    return round(x + 1e-9, 2)


def apply_pct(amount, pct):
    return round_money(amount * pct / 10)
