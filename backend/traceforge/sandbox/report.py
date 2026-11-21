"""JUnit parsing and secret redaction for sandbox output."""

import re
import xml.etree.ElementTree as ET

from traceforge.contracts.test_run import TestOutcome

_SECRET = re.compile(
    r"(?i)(?:(?:password|passwd|secret|token|api[_-]?key|authorization|bearer)\s*[=:]\s*\S+"
    r"|sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


def redact(text: str) -> str:
    return _SECRET.sub("[REDACTED]", text)


def tail(text: str, cap: int) -> str:
    """Redact first, then keep the last `cap` chars (so a secret cannot be cut in half)."""
    return redact(text)[-cap:]


def _node_id(case: ET.Element) -> str:
    file, cls, name = case.get("file") or "", case.get("classname") or "", case.get("name") or ""
    if not file:
        return f"{cls}::{name}" if cls else name
    if not cls:  # collection error: name is the module
        return file
    cls_only = cls.removeprefix(file.removesuffix(".py").replace("/", ".")).lstrip(".")
    return "::".join(p for p in (file, cls_only, name) if p)


def parse_junit(xml_text: str) -> tuple[list[TestOutcome], float]:
    """(per-test outcomes, pytest-reported seconds). Errors and collection errors are 'error'."""
    root = ET.fromstring(xml_text)
    outcomes: list[TestOutcome] = []
    for case in root.iter("testcase"):
        if case.find("failure") is not None:
            kind = "failed"
        elif case.find("error") is not None:
            kind = "error"
        elif case.find("skipped") is not None:
            kind = "skipped"
        else:
            kind = "passed"
        outcomes.append(TestOutcome(id=_node_id(case), outcome=kind))
    secs = sum(float(s.get("time") or 0) for s in root.iter("testsuite"))
    return outcomes, secs
