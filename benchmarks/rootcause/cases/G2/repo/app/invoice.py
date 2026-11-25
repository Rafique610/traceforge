from app.billing.totals import compute_total


def create_invoice(items):
    return compute_total(items)
