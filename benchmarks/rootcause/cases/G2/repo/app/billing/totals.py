def compute_total(items):
    return sum(i["prize"] * i["qty"] for i in items)
