from app.fees import fee, with_fee


def test_fee():
    assert fee(100) == 1.0


def test_with_fee():
    assert with_fee(100) == 101.0
