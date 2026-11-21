import pytest

from traceforge.evidence.redaction import redact_text, redact_value, secret_values

# Realistic strings; every secret below is a made-up value.
SECRET_TEXTS = [
    ("DB_PASSWORD=hunter2hunter2", "hunter2hunter2"),
    ("password: 'S3cr3t!pass'", "S3cr3t!pass"),
    ('{"api_key": "abc123def456ghi789"}', "abc123def456ghi789"),
    ("postgresql://shop:s3cretpw@lab_db:5432/shop", "s3cretpw"),
    ("postgresql+psycopg://shop:p%40ss@db.internal/shop?sslmode=require", "p%40ss"),
    ("redis://:redispass99@lab_redis:6379/0", "redispass99"),
    ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.c2lnbmF0dXJl", "eyJhbGci"),
    ("authorization=Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA"),
    ("GET /v1/x?access_token=tok_live_998877&page=2", "tok_live_998877"),
    ("OPENROUTER_API_KEY=sk-or-v1-0123456789abcdef0123", "sk-or-v1-0123456789abcdef0123"),
    ("using key ghp_abcdefghijklmnopqrstuvwxyz0123456789", "ghp_abcdefghijkl"),
    ("aws AKIAIOSFODNN7EXAMPLE leaked", "AKIAIOSFODNN7EXAMPLE"),
    ("client_secret = 'zzzz-9999-yyyy'", "zzzz-9999-yyyy"),
]


@pytest.mark.parametrize(("text", "secret"), SECRET_TEXTS)
def test_secrets_removed(text, secret):
    out = redact_text(text)
    assert secret not in out
    assert "«redacted:" in out


def test_dsn_keeps_host_and_scheme_only():
    out = redact_text("connect postgresql://shop:s3cretpw@lab_db:5432/shop failed")
    assert out == "connect postgresql://«redacted:dsn»@lab_db:5432/shop failed"


def test_non_secret_text_unchanged():
    for t in [
        "redis lab_redis:6379 not reachable: Error -2 connecting to lab_redis:6379.",
        'File "/app/app/orders.py", line 21, in order_total',
        'INFO:     127.0.0.1:1 - "GET /orders/7/total HTTP/1.1" 500 Internal Server Error',
        "postgresql://shop@lab_db/shop",  # user without password is not a secret
    ]:
        assert redact_text(t) == t


@pytest.mark.parametrize(
    ("key", "value", "kept"),
    [
        ("DB_PASSWORD", "x1y2z3w4", False),
        ("API_TOKEN", "abcd1234", False),
        ("SECRET_KEY", "abcd1234", False),
        ("DATABASE_URL", "postgresql://u:p@h/db", False),
        ("SENTRY_DSN", "https://abc@o1.ingest.sentry.io/1", False),
        ("REDIS_HOST", "lab_redis", True),
        ("REDIS_PORT", "6379", True),
        ("ORDER_QUEUE", "orders:confirm", True),
        ("DB_NAME", "shop", True),
    ],
)
def test_env_values(key, value, kept):
    out = redact_value(key, value)
    assert (out == value) is kept
    if not kept:
        assert value not in out


def test_dsn_under_allowlisted_name_is_stripped():
    out = redact_value("DB_HOST", "postgresql://shop:pw123456@lab_db/shop")
    assert "pw123456" not in out and "lab_db" in out


def test_known_secret_values_scrubbed_anywhere():
    env = {"DB_PASSWORD": "Tr0ub4dor&3", "DB_HOST": "lab_db", "X": "postgres://u:inner-pw-77@h/d"}
    secrets = secret_values(env)
    assert secrets == {"Tr0ub4dor&3", "inner-pw-77"}
    out = redact_text("auth failed for Tr0ub4dor&3 and inner-pw-77", secrets)
    assert "Tr0ub4dor" not in out and "inner-pw-77" not in out


def test_idempotent():
    once = redact_text("password=abcd1234 postgresql://u:pw9999@h/d")
    assert redact_text(once) == once
