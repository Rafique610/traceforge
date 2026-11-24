# ruff: noqa: E501
import pytest

from traceforge.repair import policy
from traceforge.repair.edits import (
    EditBlock,
    EditError,
    apply_edits,
    parse_blocks,
    to_unified_diff,
)

ALLOW = ["shop.py", "other.py", "pkg/mod.py"]


@pytest.mark.parametrize(
    ("path", "prefix"),
    [
        ("../evil.py", "path_escape"),
        ("pkg/../../x.py", "path_escape"),
        ("/etc/passwd", "absolute_path"),
        ("C:/x.py", "absolute_path"),
        ("tests/test_x.py", "test_file"),
        ("pkg/conftest.py", "test_file"),
        ("elsewhere.py", "not_allowlisted"),
    ],
)
def test_path_rejections(path, prefix):
    assert policy.check_paths([path], ALLOW)[0].startswith(prefix)


def test_symlink_and_too_many_files():
    assert policy.check_paths(["shop.py"], ALLOW, symlinks=["shop.py"]) == ["symlink:shop.py"]
    assert "too_many_files" in policy.check_paths(["shop.py", "other.py", "pkg/mod.py"], ALLOW)
    assert policy.check_paths(["shop.py", "other.py"], ALLOW) == []


def test_oversize_binary_syntax():
    old = {"shop.py": "x = 1\n"}
    big = {"shop.py": "".join(f"y{i} = 'v{i}'\n" for i in range(70))}
    r = policy.check_patch(to_unified_diff(old, big), old, big)
    assert "too_many_lines" in r.reasons
    bin_ = {"shop.py": "x = 1\x00\n"}
    assert "binary:shop.py" in policy.check_patch("", old, bin_).reasons
    bad = {"shop.py": "def (:\n"}
    assert "syntax_error:shop.py" in policy.check_patch("", old, bad).reasons


def test_ambiguous_and_nonmatching_blocks():
    files = {"a.py": "x = 1\nx = 1\ny = 2\n"}
    with pytest.raises(EditError) as e:
        apply_edits(files, [EditBlock("a.py", "x = 1", "x = 3")])
    assert e.value.reason == "ambiguous_match"
    with pytest.raises(EditError) as e:
        apply_edits(files, [EditBlock("a.py", "z = 9", "z = 3")])
    assert e.value.reason == "no_match"
    assert apply_edits(files, [EditBlock("a.py", "y = 2", "y = 3")])["a.py"].endswith("y = 3\n")
    with pytest.raises(EditError):
        parse_blocks("just prose")


def test_diff_roundtrip_and_signature_flag():
    old = {"a.py": "def f(a):\n    return a\n"}
    new = {"a.py": "def f(a, b):\n    return a\n"}
    d = to_unified_diff(old, new)
    assert d.startswith("diff --git a/a.py b/a.py") and "-def f(a):" in d
    assert policy.check_patch(d, old, new).signature_changed
    same = {"a.py": "def f(a):\n    return a + 4\n"}
    assert not policy.check_patch(to_unified_diff(old, same), old, same).signature_changed


def test_test_literal_catches_special_cased_input():
    visible = "def test_t():\n    assert discount(200, 10) == 180\n"
    old = {"shop.py": "def discount(p, c):\n    return p - p * c\n"}
    special = {
        "shop.py": "def discount(p, c):\n    if p == 200:\n        return 180\n    return p - p * c\n"
    }
    r = policy.check_patch(to_unified_diff(old, special), old, special, [visible])
    assert not r.ok and "test_literal:shop.py" in r.reasons
    honest = {"shop.py": "def discount(p, c):\n    return p - p * c / 100\n"}  # 100 not in test
    assert policy.check_patch(to_unified_diff(old, honest), old, honest, [visible]).ok
    # 0, 1 and '' are excluded
    trivial = {"shop.py": "def discount(p, c):\n    return p - 0 * 1\n"}
    assert policy.check_patch(to_unified_diff(old, trivial), old, trivial, ["x = 1 + 0\n"]).ok


_VISIBLE = (
    "def test_t():\n"
    "    assert discount(42, 5) == 8.4\n"
    "    assert discount(100, 10) == 90\n"
    "    assert name(7) == 'expected-literal'\n"
    "    assert f(1000, 30, 10) == 3\n"
)
_OLD = "def g(price, pct, items, x):\n    return price\n"
_H = "def g(price, pct, items, x):\n"

# (patched source, should_be_flagged)
_TABLE = [
    (_H + "    if price == 42:\n        return 8.4\n    return price\n", True),
    (_H + "    return 'expected-literal'\n", True),
    (_H + "    return {42: 8.4, 100: 90}[price]\n", True),
    (_H + "    return 5 if price in (42, 100) else 3\n", True),
    (_H + "    r = 90\n    return price\n", True),
    (_H + "    return 8.4 if price != 0 else 0\n", True),
    (_H + "    match price:\n        case 42:\n            return 3\n    return price\n", True),
    (_H + "    return price * pct / 100\n", False),
    (_H + "    return x * 1000\n", False),
    ("def g(price, pct, items, x, timeout=30):\n    return price\n", False),
    (_H + "    return items[:10]\n", False),
    (_H + "    return round(price, 10) - 7 + 0 * 1\n", False),
    (_H + "    return price if price > 42 else -1\n", False),
    (_H + "    return price == 'a' or x == ''\n", False),
]


def test_test_literal_table_no_false_positives_or_negatives():
    fp = fn = 0
    for src, flagged in _TABLE:
        new = {"shop.py": src}
        r = policy.check_patch(
            to_unified_diff({"shop.py": _OLD}, new), {"shop.py": _OLD}, new, [_VISIBLE]
        )
        got = "test_literal:shop.py" in r.reasons
        fp += got and not flagged
        fn += flagged and not got
    assert (fp, fn) == (0, 0)


def test_test_literal_only_added_literals_count():
    old = {"shop.py": "def g(x):\n    if x == 42:\n        return 8.4\n    return x\n"}
    new = {"shop.py": "def g(x):\n    if x == 42:\n        return 8.4\n    return x + 1\n"}
    assert policy.check_patch(to_unified_diff(old, new), old, new, [_VISIBLE]).ok


def test_class_level_field_default_is_not_a_test_literal_but_module_constants_still_are():
    """Settings defaults are configuration: the fix is the value itself (found on the frozen split:
    the gold fix of 29 configuration cases was rejected by the literal rule before this)."""
    visible = 'def test_t(s):\n    assert s.queue == "orders:confirm"\n'
    old = {"settings.py": 'class Settings:\n    queue: str = "wrong"\n'}
    fixed = {"settings.py": 'class Settings:\n    queue: str = "orders:confirm"\n'}
    assert policy.check_patch(to_unified_diff(old, fixed), old, fixed, [visible]).ok
    old2 = {"m.py": 'QUEUE = "wrong"\n'}
    fixed2 = {"m.py": 'QUEUE = "orders:confirm"\n'}
    r = policy.check_patch(to_unified_diff(old2, fixed2), old2, fixed2, [visible])
    assert (
        not r.ok and "test_literal:m.py" in r.reasons
    )  # a module-level assignment is still checked
