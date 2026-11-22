"""Order totals and counts as shown on the order summary."""

from conftest import observe_total


def test_total_1(client, session):
    assert observe_total(client, session, [("6.15", 5), ("36.25", 1)]) == [200, "67.00", 6, "11.17", "Item 1"]


def test_total_2(client, session):
    assert observe_total(client, session, [("50.00", 1), ("36.25", 6), ("36.25", 2)]) == [200, "340.00", 9, "37.78", "Item 1"]


def test_total_3(client, session):
    assert observe_total(client, session, [("27.90", 5), ("36.25", 2)]) == [200, "212.00", 7, "30.29", "Item 1"]
