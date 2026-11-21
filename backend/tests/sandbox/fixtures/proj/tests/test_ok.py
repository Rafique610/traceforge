from shop import ident


def test_ident():
    assert ident(7) == 7


class TestGroup:
    def test_ident_str(self):
        assert ident("a") == "a"
