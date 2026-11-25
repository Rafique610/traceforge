def compute_total(rows):
    return sum(r["amount"] for r in rows)
