from app.rates import lookup


def test_lookup():
    assert lookup("EUR") == 0.9
