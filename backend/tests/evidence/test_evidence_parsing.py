from pathlib import Path

from traceforge.evidence import logs
from traceforge.evidence.traces import parse_tracebacks

FIX = Path(__file__).parent / "fixtures"


def _recs(name):
    return logs.group_records((FIX / name).read_text("utf-8").splitlines())


def test_real_nested_traceback_shop_api_db_down():
    """Captured from the real lab: SQLAlchemy `raise ... from e` chain, DB container stopped."""
    text = (FIX / "shop_api_db_down.log").read_text("utf-8")
    tbs = parse_tracebacks("\n".join(logs.split_line(ln)[1] for ln in text.splitlines()))
    frames = [f for tb in tbs for f in tb.frames]
    mine = [(f.path, f.line, f.function) for f in frames if f.path.startswith("/app/")]
    assert ("/app/app/routes/products.py", 13, "list_products") in mine
    assert ("/app/app/catalog.py", 9, "list_products") in mine
    last = [tb for tb in tbs if tb.exception][-1]
    assert last.exception.startswith("sqlalchemy.exc.OperationalError")
    assert "lab_db" in last.exception
    assert any(f.external for f in frames)
    assert not any(f.external for f in frames if f.path.startswith("/app/"))
    assert any(f.code and "session.scalars" in f.code for f in frames)


def test_real_worker_chain_is_one_record_two_tracebacks():
    """Captured from the real lab: wrong REDIS_HOST; socket.gaierror then ConnectionError."""
    recs = _recs("worker_bad_redis.log")
    tb_recs = [r for r in recs if r.tracebacks]
    assert len(tb_recs) == 1
    tbs = tb_recs[0].tracebacks
    assert len(tbs) == 2
    assert tbs[0].exception.startswith("socket.gaierror")
    assert tbs[1].exception.startswith("redis.exceptions.ConnectionError")
    assert [(f.path, f.line) for f in tbs[1].frames if f.path.startswith("/app/")] == [
        ("/app/worker/main.py", 36),
        ("/app/worker/main.py", 28),
        ("/app/worker/queue.py", 41),
        ("/app/worker/retry.py", 18),
        ("/app/worker/queue.py", 36),
    ]
    assert tb_recs[0].ts is not None


def test_real_plain_worker_log_format_and_ts():
    recs = _recs("worker_bad_redis.log")
    assert logs.detect_format(recs) == "plain"
    assert recs[0].ts is not None and recs[0].ts.tzinfo is not None


def test_json_logs_exc_info_and_structured_stack():
    recs = _recs("api_json_exc.log")
    assert logs.detect_format(recs) == "json"
    assert recs[0].request_id == "req-7f3a9c21" and recs[0].ts.year == 2026
    exc = recs[1].tracebacks[0]
    assert [(f.path, f.line, f.function) for f in exc.frames] == [
        ("/app/app/routes/orders.py", 30, "order_total_route"),
        ("/app/app/orders.py", 21, "order_total"),
    ]
    assert exc.exception == "IndexError: list index out of range"
    stack = recs[2].tracebacks[0]  # the malformed dict (filename=5) is skipped, not invented
    assert [(f.path, f.line, f.function) for f in stack.frames] == [
        ("/app/app/pricing.py", 12, "money")
    ]
    assert recs[-1].kind == "plain"  # malformed JSON stays a plain line


def test_uvicorn_access_format():
    recs = _recs("api_access_only.log")
    assert logs.detect_format(recs) == "uvicorn_access"
    assert [r.status for r in recs] == [201, 500, 200]
    assert not any(r.tracebacks for r in recs)


def test_none_format_for_empty():
    assert logs.detect_format(logs.group_records([])) == "none"
    assert logs.group_records(["", "  ", ""]) == []


def test_truncated_traceback_and_malformed_frame_not_invented():
    recs = _recs("truncated.log")
    rec = next(r for r in recs if r.tracebacks)
    tb = rec.tracebacks[0]
    assert [(f.path, f.line) for f in tb.frames] == [("/app/app/orders.py", 21)]
    assert tb.exception is None and not tb.complete
    assert recs[-1].kind == "access"  # the next log line is not swallowed as an exception line
    assert "Exception in ASGI application" in rec.text


def test_window_cut_mid_traceback_keeps_frames():
    lines = [
        "        return fn()",
        '  File "/app/app/catalog.py", line 9, in list_products',
        "    return x",
        "sqlalchemy.exc.OperationalError: boom",
        'INFO:     1.1.1.1:5 - "GET /products HTTP/1.1" 500 Internal Server Error',
    ]
    recs = logs.group_records(lines)
    assert recs[0].tracebacks[0].frames[0].line == 9
    assert recs[0].tracebacks[0].exception == "sqlalchemy.exc.OperationalError: boom"
    assert recs[1].kind == "access"


def test_missing_function_and_no_traceback():
    assert parse_tracebacks("hello\nworld") == []
    assert parse_tracebacks('File "/a/b.py", line 3')[0].frames[0].function is None


def test_window_caps_lines_and_bytes():
    text = "\n".join(f"line {i:04d} " + "x" * 90 for i in range(1000))
    lines, cut = logs.window(text, 400, 4096)
    assert cut and len(lines) < 50 and lines[-1].startswith("line 0999")
    lines, cut = logs.window("a\nb", 400, 4096)
    assert lines == ["a", "b"] and not cut


def test_blocks_split_on_blank_cap_and_traceback():
    lines = ["a", "b", "", "c"] + [f"x{i}" for i in range(30)]
    lines += ["Traceback (most recent call last):", '  File "/app/a.py", line 1, in f']
    lines += ["ValueError: v"]
    blocks = logs.make_blocks(logs.group_records(lines), 25)
    sizes = [sum(r.lines for r in b) for b in blocks[:-1]]
    assert sizes[0] == 2 and max(sizes) <= 25
    assert blocks[-1][0].tracebacks and len(blocks[-1]) == 1
