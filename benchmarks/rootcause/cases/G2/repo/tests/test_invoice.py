from app.invoice import create_invoice


def test_invoice_total():
    assert create_invoice([{"price": 10, "qty": 3}]) == 30
