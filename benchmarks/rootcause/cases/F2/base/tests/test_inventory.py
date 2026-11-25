import pytest

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
