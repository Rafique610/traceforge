from shop import add


def test_hidden_add():
    assert add(10, 5) == 15


def test_hidden_zero():
    assert add(0, 0) == 0
