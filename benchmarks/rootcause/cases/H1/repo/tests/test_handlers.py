from app.handlers import handle


def test_refund():
    assert handle({"kind": "refund", "order": {"total": 10}}) == -10
