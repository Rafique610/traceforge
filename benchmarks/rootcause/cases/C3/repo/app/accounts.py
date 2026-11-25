from app import settings
from app.fees import with_fee


class Account:
    def __init__(self, owner, balance=0, currency=None):
        self.owner = owner
        self.balance = balance
        self.currency = currency or settings.DEFAULT_CURRENCY

    def deposit(self, amount):
        self.balance = round(self.balance + amount, 2)

    def _debit(self, amount):
        cost = with_fee(amount)
        if cost > self.balance:
            raise ValueError("insufficient funds")
        self.balance = round(self.balance - cost, 2)
        return cost

    def withdraw(self, amount):
        return self._debit(amount)


class SavingsAccount(Account):
    LIMIT = 500

    def withdraw(self, amount):
        if amount > self.LIMIT:
            raise ValueError("over savings limit")
        return self._debit(amount)
