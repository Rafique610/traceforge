"""Order totals and counts as shown on the order summary."""

from conftest import observe_total


def test_total_1(client, session):
    assert observe_total(client, session, [("18.75", 2)]) == [200, '37.50', 2, '18.75', 'Item 1']


def test_total_2(client, session):
    assert observe_total(client, session, [("12.00", 4), ("18.75", 3)]) == [200, '104.25', 7, '14.89', 'Item 1']
