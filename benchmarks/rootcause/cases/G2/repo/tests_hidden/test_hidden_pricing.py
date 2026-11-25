from app.pricing import gross


def test_hidden_gross():
    assert gross(10, 1) == 12
