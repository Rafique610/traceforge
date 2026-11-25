from app.convert import convert


def test_convert_usd_eur():
    assert convert(100, "USD", "EUR") == 90.0


def test_convert_eur_usd():
    assert convert(90, "EUR", "USD") == 100.0
