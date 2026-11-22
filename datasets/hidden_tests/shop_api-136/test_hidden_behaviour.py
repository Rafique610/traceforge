"""Order totals and counts as shown on the order summary."""

from conftest import observe_total


def test_total_1(client, session):
    assert observe_total(client, session, [("50.00", 5), ("36.25", 5)]) == [200, '431.25', 10, '43.13', 'Item 1']
