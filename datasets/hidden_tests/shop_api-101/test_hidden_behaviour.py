"""Order totals and counts as shown on the order summary."""

from conftest import observe_total


def test_total_1(client, session):
    assert observe_total(client, session, [("2.85", 2), ("64.80", 6)]) == [200, '394.50', 8, '49.31', 'Item 1']


def test_total_2(client, session):
    assert observe_total(client, session, [("15.50", 6), ("9.99", 1), ("9.99", 6)]) == [200, '162.93', 13, '12.53', 'Item 1']


def test_total_3(client, session):
    assert observe_total(client, session, [("50.00", 5), ("21.05", 6), ("2.85", 6)]) == [200, '393.40', 17, '23.14', 'Item 1']
