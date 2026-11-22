"""Order totals and counts as shown on the order summary."""

from conftest import observe_total


def test_total_1(client, session):
    assert observe_total(client, session, [("36.25", 2)]) == [200, '72.50', 2, '36.25', 'Item 1']


def test_total_2(client, session):
    assert observe_total(client, session, [("2.85", 2), ("64.80", 6)]) == [200, '394.50', 8, '49.31', 'Item 1']


def test_total_3(client, session):
    assert observe_total(client, session, [("36.25", 2), ("9.99", 2)]) == [200, '92.48', 4, '23.12', 'Item 1']
