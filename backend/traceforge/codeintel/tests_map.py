"""Which files and functions are tests. Test -> function edges (tests_covers) come from assemble.

A test function is `test*` in a test file. Its resolved calls become `tests_covers` edges
(confidence 1.0/0.9); names of imported functions/classes it references without calling
(monkeypatch targets, fixtures) become `tests_covers` with confidence 0.6.
"""

import re

_TEST_FILE = re.compile(
    r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$"
)


def is_test_file(rel: str) -> bool:
    return bool(_TEST_FILE.search(rel))


def is_test_name(name: str) -> bool:
    return name.lower().startswith("test")
