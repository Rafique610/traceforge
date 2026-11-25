import pytest

from app.accounts import Account, SavingsAccount


def test_deposit():
    a = Account("a")
    a.deposit(5)
    assert a.balance == 5


def test_withdraw_cost():
    a = Account("a", 200)
    assert a.withdraw(100) == 101.0
    assert a.balance == 99.0


def test_savings_withdraw():
    s = SavingsAccount("s", 1000)
    assert s.withdraw(100) == 101.0
    assert s.balance == 899.0


def test_savings_limit():
    s = SavingsAccount("s", 1000)
    with pytest.raises(ValueError):
        s.withdraw(600)
