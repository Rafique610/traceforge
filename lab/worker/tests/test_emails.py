from worker.emails import render_confirmation


def test_render_confirmation():
    assert (
        render_confirmation(7, "14.50")
        == "Your order #7 is confirmed. Total charged: 14.50."
    )
