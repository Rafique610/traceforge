from app.reports.summary import daily_summary


def test_daily_summary():
    assert daily_summary([{"amount": 5}, {"amount": 7}]) == {"total": 12}
