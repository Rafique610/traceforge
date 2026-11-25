from app.money import apply_pct, round_money


def test_round_money():
    assert round_money(1.005) == 1.01


def test_apply_pct():
    assert apply_pct(200, 10) == 20
