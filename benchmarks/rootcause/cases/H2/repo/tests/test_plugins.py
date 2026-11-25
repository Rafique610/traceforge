from app.plugins import run


def test_double_plugin():
    assert run("double", 4) == 8
