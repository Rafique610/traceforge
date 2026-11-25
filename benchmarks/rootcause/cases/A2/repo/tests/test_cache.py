from app.cache import connect


def test_connect():
    assert connect().set("k", 1) is True
