"""Clean mini projects (lab-style) used as the base of every case. All visible tests PASS here.

Hand-written; the bug of each case is a text edit listed in cases.py. Two projects:
  S "shop":   settings/money/pricing/inventory/cache/orders + compose (env loaded by conftest)
  L "ledger": settings/rates/convert/fees/accounts(inheritance)/transfer/report + compose
"""

CONFTEST = '''import os
import pathlib

import yaml

_doc = yaml.safe_load((pathlib.Path(__file__).resolve().parent.parent / "compose.yaml").read_text())
for _k, _v in (_doc["services"]["{svc}"].get("environment") or {{}}).items():
    os.environ[_k] = str(_v)
'''

PYTEST_INI = "[pytest]\ntestpaths = tests\n"

SHOP = {
    "pytest.ini": PYTEST_INI,
    "compose.yaml": """services:
  api:
    build: .
    command: python -m app.orders
    environment:
      CACHE_HOST: cache
      CACHE_PORT: "6379"
      TAX_RATE: "0.2"
  cache:
    image: redis:7
""",
    "app/__init__.py": "",
    "app/settings.py": '''import os

TAX_RATE = float(os.getenv("TAX_RATE", "0.2"))
CACHE_HOST = os.getenv("CACHE_HOST", "cache")
CACHE_PORT = int(os.getenv("CACHE_PORT", "6379"))
MAX_QTY = int(os.getenv("MAX_QTY", "100"))
''',
    "app/money.py": '''def round_money(x):
    return round(x + 1e-9, 2)


def apply_pct(amount, pct):
    return round_money(amount * pct / 100)
''',
    "app/pricing.py": '''from app import settings
from app.money import apply_pct, round_money


def net_price(price, qty):
    return round_money(price * qty)


def discount(amount, pct):
    return round_money(amount - apply_pct(amount, pct))


def tax(amount):
    return round_money(amount * settings.TAX_RATE)


def gross(price, qty, pct=0):
    net = discount(net_price(price, qty), pct)
    return round_money(net + tax(net))
''',
    "app/inventory.py": '''from app import settings


class Stock:
    def __init__(self):
        self.items = {}

    def add(self, sku, qty):
        self.items[sku] = self.available(sku) + qty

    def available(self, sku):
        return self.items.get(sku, 0)

    def reserve(self, sku, qty):
        if qty > settings.MAX_QTY:
            raise ValueError("qty above limit")
        if qty > self.available(sku):
            raise ValueError("insufficient stock")
        self.items[sku] = self.available(sku) - qty
''',
    "app/cache.py": '''from app import settings

SERVER = ("cache", 6379)


class Client:
    def __init__(self, host, port):
        if (host, port) != SERVER:
            raise ConnectionError(f"cannot reach host {host!r} port {port}")
        self.data = {}

    def set(self, key, value):
        self.data[key] = value
        return True


def connect():
    return Client(settings.CACHE_HOST, settings.CACHE_PORT)
''',
    "app/orders.py": '''from app import cache
from app.pricing import gross


def quote(price, qty, pct=0):
    return gross(price, qty, pct)


def create_order(stock, sku, price, qty, pct=0):
    stock.reserve(sku, qty)
    total = gross(price, qty, pct)
    cache.connect().set(f"order:{sku}", total)
    return total
''',
    "tests/conftest.py": CONFTEST.format(svc="api"),
    "tests/test_money.py": '''from app.money import apply_pct, round_money


def test_round_money():
    assert round_money(1.005) == 1.01


def test_apply_pct():
    assert apply_pct(200, 10) == 20
''',
    "tests/test_pricing.py": '''from app.pricing import discount, gross, net_price, tax


def test_net_price():
    assert net_price(10, 3) == 30


def test_discount():
    assert discount(200, 10) == 180


def test_tax():
    assert tax(100) == 20


def test_gross_plain():
    assert gross(100, 1) == 120


def test_gross_with_discount():
    assert gross(100, 2, 10) == 216
''',
    "tests/test_inventory.py": '''import pytest

from app.inventory import Stock


def test_reserve_exact():
    s = Stock()
    s.add("A", 5)
    s.reserve("A", 5)
    assert s.available("A") == 0


def test_insufficient():
    s = Stock()
    s.add("A", 1)
    with pytest.raises(ValueError):
        s.reserve("A", 2)
''',
    "tests/test_cache.py": '''from app.cache import connect


def test_connect():
    assert connect().set("k", 1) is True
''',
    "tests/test_orders.py": '''from app.inventory import Stock
from app.orders import create_order, quote


def test_quote():
    assert quote(50, 2, 10) == 108.0


def test_create_order():
    s = Stock()
    s.add("A", 10)
    assert create_order(s, "A", 100, 2, 10) == 216.0
    assert s.available("A") == 8


def test_create_order_exact_stock():
    s = Stock()
    s.add("B", 3)
    assert create_order(s, "B", 10, 3) == 36.0


def test_create_order_after_two_adds():
    s = Stock()
    s.add("C", 2)
    s.add("C", 3)
    assert create_order(s, "C", 10, 5) == 60.0
''',
    "tests_hidden/test_hidden_pricing.py": '''from app.pricing import gross


def test_hidden_gross():
    assert gross(10, 1) == 12
''',
}

LEDGER = {
    "pytest.ini": PYTEST_INI,
    "compose.yaml": """services:
  ledger:
    build: .
    command: python -m app.transfer
    environment:
      FEE_RATE: "0.01"
      DEFAULT_CURRENCY: USD
  db:
    image: postgres:16
""",
    "app/__init__.py": "",
    "app/settings.py": '''import os

FEE_RATE = float(os.getenv("FEE_RATE", "0.01"))
DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "USD")
''',
    "app/rates.py": '''RATES = {"USD": 1.0, "EUR": 0.9, "GBP": 0.8}


def lookup(currency):
    return RATES[currency]
''',
    "app/convert.py": '''from app.rates import lookup


def convert(amount, src, dst):
    return round(amount / lookup(src) * lookup(dst), 2)
''',
    "app/fees.py": '''from app import settings


def fee(amount):
    return round(amount * settings.FEE_RATE, 2)


def with_fee(amount):
    return round(amount + fee(amount), 2)
''',
    "app/accounts.py": '''from app import settings
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
''',
    "app/transfer.py": '''from app.convert import convert


def transfer(src, dst, amount):
    converted = convert(amount, src.currency, dst.currency)
    src.withdraw(amount)
    dst.deposit(converted)
    return converted
''',
    "app/report.py": '''from app.convert import convert


def total_usd(accounts):
    return round(sum(convert(a.balance, a.currency, "USD") for a in accounts), 2)
''',
    "tests/conftest.py": CONFTEST.format(svc="ledger"),
    "tests/test_rates.py": '''from app.rates import lookup


def test_lookup():
    assert lookup("EUR") == 0.9
''',
    "tests/test_convert.py": '''from app.convert import convert


def test_convert_usd_eur():
    assert convert(100, "USD", "EUR") == 90.0


def test_convert_eur_usd():
    assert convert(90, "EUR", "USD") == 100.0
''',
    "tests/test_fees.py": '''from app.fees import fee, with_fee


def test_fee():
    assert fee(100) == 1.0


def test_with_fee():
    assert with_fee(100) == 101.0
''',
    "tests/test_accounts.py": '''import pytest

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
''',
    "tests/test_transfer.py": '''from app.accounts import Account
from app.transfer import transfer


def test_transfer_converts():
    a = Account("a", 500, "USD")
    b = Account("b", 0, "EUR")
    assert transfer(a, b, 100) == 90.0
    assert a.balance == 399.0
    assert b.balance == 90.0
''',
    "tests/test_report.py": '''from app.accounts import Account
from app.report import total_usd


def test_total_usd():
    assert total_usd([Account("a", 90, "EUR"), Account("b", 10, "USD")]) == 110.0
''',
    "tests_hidden/test_hidden_fees.py": '''from app.fees import fee


def test_hidden_fee():
    assert fee(200) == 2.0
''',
}

PROJECTS = {"S": SHOP, "L": LEDGER}
