from app.accounts import Account
from app.transfer import transfer


def test_transfer_converts():
    a = Account("a", 500, "USD")
    b = Account("b", 0, "EUR")
    assert transfer(a, b, 100) == 90.0
    assert a.balance == 399.0
    assert b.balance == 90.0
