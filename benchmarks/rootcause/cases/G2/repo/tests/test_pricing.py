from app.pricing import discount, gross, net_price, tax


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
