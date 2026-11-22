"""Order totals and counts as shown on the order summary."""

from conftest import observe_total


def test_total_1(client, session):
    assert observe_total(client, session, [("49.99", 2), ("18.75", 2), ("24.10", 1)]) == [200, "161.58", 5, "32.32", "Item 1"]


def test_total_2(client, session):
    assert observe_total(client, session, [("7.45", 3), ("41.60", 3)]) == [200, "147.15", 6, "24.53", "Item 1"]
