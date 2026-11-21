"""Log windowing, record grouping, format detection and block splitting.

A *record* is one logical log entry (a plain line, a JSON line, or a traceback with its header).
A *block* is what becomes one evidence item: a traceback record alone, or a run of consecutive
non-traceback records (split on blank lines, capped at `block_max_lines`).
"""

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from traceforge.evidence.traces import (
    CHAIN_RE,
    FRAME_RE,
    TB_START,
    Frame,
    Traceback,
    is_exception_name,
    parse_tracebacks,
)

LogFormat = Literal["plain", "json", "uvicorn_access", "none"]
_DOCKER_TS = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z)\s?")
_LEAD_TS = re.compile(r"^(\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d(?:[.,]\d+)?)")
ACCESS_RE = re.compile(
    r'^(?:INFO|WARNING|ERROR):\s+(?P<client>\S+) - "(?P<method>[A-Z]+) (?P<target>\S+) '
    r'HTTP/[\d.]+" (?P<status>\d{3})'
)
_REQ_ID = re.compile(
    r"(?i)\b(?:x-request-id|request[_-]?id|req[_-]?id)[=:\s\"']+([A-Za-z0-9_\-]{6,})"
)
_TS_KEYS = ("ts", "timestamp", "time", "asctime", "@timestamp")
_TB_KEYS = ("exc_info", "exception", "stack_trace", "stack", "traceback")
_RID_KEYS = ("request_id", "req_id", "x_request_id", "trace_id", "correlation_id")


@dataclass
class Record:
    text: str
    ts: datetime | None = None
    kind: Literal["plain", "json", "access"] = "plain"
    lines: int = 1
    request_id: str | None = None
    after_blank: bool = False
    in_tb: bool = False  # text contains a printed traceback (parsed in finalize)
    tracebacks: list[Traceback] = field(default_factory=list)
    status: int | None = None  # access records


def parse_ts(s: str | None) -> datetime | None:
    if not isinstance(s, str):
        return None
    try:
        d = datetime.fromisoformat(s.strip().replace(",", ".").replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def split_line(raw: str) -> tuple[datetime | None, str]:
    """Strip the Docker `timestamps=True` prefix; a leading app timestamp is read but kept."""
    raw = raw.rstrip("\r\n")
    m = _DOCKER_TS.match(raw)
    if m:
        return parse_ts(m[1]), raw[m.end() :]
    m = _LEAD_TS.match(raw)
    return (parse_ts(m[1].replace(" ", "T")) if m else None), raw


def window(text: str, max_lines: int, max_bytes: int) -> tuple[list[str], bool]:
    """Last `max_lines` lines, then the newest fitting `max_bytes`. Returns (lines, truncated)."""
    lines = text.splitlines()
    cut = len(lines) > max_lines
    lines = lines[-max_lines:]
    total, keep = 0, []
    for ln in reversed(lines):
        total += len(ln.encode("utf-8", "replace")) + 1
        if total > max_bytes:
            cut = True
            break
        keep.append(ln)
    return keep[::-1], cut


def _dict_frames(items: list[Any]) -> list[Frame]:
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        path = it.get("filename") or it.get("file") or it.get("path")
        line = it.get("lineno") or it.get("line")
        if isinstance(path, str) and isinstance(line, int) and line >= 1:
            fn = it.get("name") or it.get("function") or it.get("func")
            code = it.get("line_text") or it.get("code")
            out.append(
                Frame(
                    path,
                    line,
                    fn if isinstance(fn, str) else None,
                    code if isinstance(code, str) else None,
                )
            )
    return out


def _json_record(ts: datetime | None, body: str) -> Record | None:
    if not body.lstrip().startswith("{"):
        return None
    try:
        obj = json.loads(body)
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    rec = Record(text=body, ts=ts, kind="json")
    rec.ts = next((d for k in _TS_KEYS if k in obj and (d := parse_ts(str(obj[k])))), ts)
    rec.request_id = next((str(obj[k]) for k in _RID_KEYS if obj.get(k)), None)
    for k in _TB_KEYS:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            rec.tracebacks += parse_tracebacks(v)
        elif isinstance(v, list) and (fr := _dict_frames(v)):
            rec.tracebacks.append(Traceback(frames=fr))
    return rec


def _continues(state: str, body: str) -> str | None:
    """New traceback state if `body` continues the open traceback record, else None."""
    if TB_START.match(body):
        return "open"
    if FRAME_RE.match(body) or CHAIN_RE.match(body) or body.startswith((" ", "\t", "(Background")):
        return state
    if state == "open" and is_exception_name(body.split(":", 1)[0].strip()):
        return "after"
    return None


def group_records(lines: list[str]) -> list[Record]:
    """Group raw (docker-timestamped) lines into records; never drops or rewrites content."""
    recs: list[Record] = []
    state = "none"  # none | open (inside frames) | after (exception line seen)
    blank = False
    for raw in lines:
        ts, body = split_line(raw)
        if not body.strip():
            if state == "none":
                blank = True
            else:
                recs[-1].text += "\n"
                recs[-1].lines += 1
            continue
        nxt = _continues(state, body) if state != "none" else None
        if nxt:
            recs[-1].text += "\n" + body
            recs[-1].lines += 1
            state = nxt
            continue
        state = "none"
        # a window cut can start mid-traceback: headerless frames/indented lines open a traceback
        if not recs and body.startswith((" ", "\t")) or FRAME_RE.match(body):
            recs.append(Record(text=body, ts=ts, after_blank=blank, in_tb=True))
            state, blank = "open", False
            continue
        if TB_START.match(body):
            prev = recs[-1] if recs else None
            if prev and prev.kind == "plain" and prev.lines == 1 and not blank and not prev.in_tb:
                prev.text += (
                    "\n" + body
                )  # header line such as "ERROR: Exception in ASGI application"
                prev.lines += 1
                prev.in_tb, state = True, "open"
                continue
            recs.append(Record(text=body, ts=ts, after_blank=blank, in_tb=True))
            state, blank = "open", False
            continue
        rec = _json_record(ts, body)
        if rec is None:
            m = ACCESS_RE.match(body)
            rec = Record(
                text=body,
                ts=ts,
                kind="access" if m else "plain",
                status=int(m["status"]) if m else None,
            )
            rm = _REQ_ID.search(body)
            rec.request_id = rm[1] if rm else None
        rec.after_blank, blank = blank, False
        recs.append(rec)
    for r in recs:
        if r.in_tb:
            r.tracebacks = parse_tracebacks(r.text)
            rm = _REQ_ID.search(r.text)
            r.request_id = rm[1] if rm else None
    return recs


def detect_format(recs: list[Record]) -> LogFormat:
    if not recs:
        return "none"
    n = len(recs)
    if sum(r.kind == "json" for r in recs) * 2 >= n:
        return "json"
    if sum(r.kind == "access" for r in recs) * 2 >= n:
        return "uvicorn_access"
    return "plain"


def make_blocks(recs: list[Record], max_lines: int) -> list[list[Record]]:
    """Traceback records stand alone; other records merge until a blank line or the line cap."""
    blocks: list[list[Record]] = []
    run: list[Record] = []
    n = 0
    for r in recs:
        if r.tracebacks:
            if run:
                blocks.append(run)
            blocks.append([r])
            run, n = [], 0
            continue
        if run and (r.after_blank or n + r.lines > max_lines):
            blocks.append(run)
            run, n = [], 0
        run.append(r)
        n += r.lines
    if run:
        blocks.append(run)
    return blocks
