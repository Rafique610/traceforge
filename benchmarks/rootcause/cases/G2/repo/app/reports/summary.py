from app.reports.totals import compute_total


def daily_summary(rows):
    return {"total": compute_total(rows)}
