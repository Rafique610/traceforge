from app.accounts import Account
from app.report import total_usd


def test_total_usd():
    assert total_usd([Account("a", 90, "EUR"), Account("b", 10, "USD")]) == 110.0
