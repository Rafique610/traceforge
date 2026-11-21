"""Python traceback parser: exact frames (path, line, function) from raw text. Never invents fields.

Handles multi-line tracebacks, chained exceptions (`During handling...`, `raise ... from`),
truncated tracebacks (frames kept, no exception line) and malformed frame lines (skipped).
"""

import re
from dataclasses import dataclass, field

FRAME_RE = re.compile(
    r'^\s*File "(?P<path>[^"]+)", line (?P<line>\d+)(?:, in (?P<func>\S.*?))?\s*$'
)
TB_START = re.compile(r"^\s*Traceback \(most recent call last\):\s*$")
CHAIN_RE = re.compile(
    r"^(During handling of the above exception, another exception occurred:"
    r"|The above exception was the direct cause of the following exception:)\s*$"
)
_CARET = re.compile(r"^\s*[\^~]+\s*$")
_EXC_LINE = re.compile(r"^(?P<type>[A-Za-z_][\w.]*)(?::\s?(?P<msg>.*))?$")
EXTERNAL_MARKERS = (
    "site-packages/",
    "dist-packages/",
    "/usr/lib/python",
    "/usr/local/lib/python",
    "<frozen ",
)


@dataclass
class Frame:
    path: str  # as printed (container path)
    line: int
    function: str | None
    code: str | None  # source line printed under the frame, if any
    exception: str | None = None  # "Type: message" on the innermost frame of a traceback
    segment: int = 0  # index of the traceback within a chain (0 = first printed)

    @property
    def external(self) -> bool:
        return any(m in self.path.replace("\\", "/") for m in EXTERNAL_MARKERS)

    def text(self) -> str:
        out = f'File "{self.path}", line {self.line}' + (
            f", in {self.function}" if self.function else ""
        )
        if self.code:
            out += f"\n    {self.code}"
        if self.exception:
            out += f"\n{self.exception}"
        return out


@dataclass
class Traceback:
    frames: list[Frame] = field(default_factory=list)
    exception: str | None = None
    complete: bool = False  # exception line seen


def is_exception_name(name: str) -> bool:
    """CamelCase final segment (`OperationalError`); excludes level words such as `INFO`."""
    last = name.rsplit(".", 1)[-1]
    if last[:1].isupper():
        return any(c.islower() for c in last)
    return "." in name and last.isalpha()  # e.g. socket.gaierror


def is_traceback_line(line: str) -> bool:
    return bool(TB_START.match(line) or FRAME_RE.match(line))


def parse_tracebacks(text: str) -> list[Traceback]:
    """All tracebacks in `text`, in printed order. Frames without a preceding header still parse."""
    out: list[Traceback] = []
    cur: Traceback | None = None
    last: Frame | None = None
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if TB_START.match(line):
            cur = Traceback()
            out.append(cur)
            last = None
            continue
        m = FRAME_RE.match(line)
        if m:
            if cur is None or cur.complete:
                cur = Traceback()
                out.append(cur)
            last = Frame(m["path"], int(m["line"]), m["func"], None, segment=len(out) - 1)
            cur.frames.append(last)
            continue
        if cur is None or not line.strip() or CHAIN_RE.match(line) or _CARET.match(line):
            continue
        if line.startswith((" ", "\t")):
            if last is not None and last.code is None and not cur.complete:
                last.code = line.strip()  # first indented line after a frame is its source line
            continue
        if not cur.complete and cur.frames:
            e = _EXC_LINE.match(line)
            if e and is_exception_name(e["type"]):
                cur.exception, cur.complete = line.strip(), True
                cur.frames[-1].exception = cur.exception
    return [t for t in out if t.frames]
