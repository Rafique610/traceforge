from app.fees import fee


def test_hidden_fee():
    assert fee(200) == 2.0
