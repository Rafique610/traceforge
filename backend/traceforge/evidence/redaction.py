"""Secret redaction. Pure functions; run on every text BEFORE an item is built or hashed.

Placeholder: `«redacted:<type>»`. Key rule (env/config): PASSWORD|SECRET|TOKEN|KEY|DSN|URL.
Text rules: DSN credentials, Authorization/Bearer, secret-looking key=value / JSON pairs,
known token shapes, and literal secret values learned from the environment.
"""

import re
from collections.abc import Iterable

SECRET_KEY_RE = re.compile(
    r"PASSWORD|PASSWD|PWD|SECRET|TOKEN|KEY|DSN|URL|CREDENTIAL|AUTH", re.IGNORECASE
)


def mark(kind: str) -> str:
    return f"«redacted:{kind}»"


def secret_kind(key: str) -> str | None:
    """Type of secret a config key name denotes, or None."""
    k = key.upper()
    for needle, kind in (
        ("PASSWORD", "password"),
        ("PASSWD", "password"),
        ("PWD", "password"),
        ("SECRET", "secret"),
        ("TOKEN", "token"),
        ("DSN", "dsn"),
        ("URL", "url"),
        ("CREDENTIAL", "credential"),
        ("AUTH", "authorization"),
        ("KEY", "api_key"),
    ):
        if needle in k:
            return kind
    return None


_DSN = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.\-]*://)(?P<user>[^\s/:@'\"]*)(?::(?P<pw>[^\s/@'\"]*))?@"
)
_AUTH_HDR = re.compile(
    r"(?P<k>\bauthorization\b[\"']?\s*[:=]\s*[\"']?)(?:(?:bearer|basic|token|digest)\s+)?[^\s\"',;}]+",
    re.IGNORECASE,
)
_BEARER = re.compile(r"\b(?:bearer|basic)\s+[A-Za-z0-9\-._~+/=]{8,}", re.IGNORECASE)
_PAIR = re.compile(
    r"(?P<k>[\"']?[\w.\-]*(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key"
    r"|private[_-]?key|credential|dsn)[\w.\-]*[\"']?\s*[:=]\s*)"
    r"(?P<v>\"[^\"]*\"|'[^']*'|[^\s,;&}\"']+)",
    re.IGNORECASE,
)
_SHAPES = (
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), "api_key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "token"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"), "token"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "api_key"),
    (re.compile(r"\b(?:hf|gsk)_[A-Za-z0-9]{20,}"), "api_key"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]*"), "token"),
)
_ALREADY = "«redacted:"


def _pair(m: re.Match[str]) -> str:
    v = m.group("v")
    if v.strip("\"'").startswith(_ALREADY):
        return m.group(0)
    kind = secret_kind(m.group("k")) or "secret"
    q = v[0] if v[0] in "\"'" and v[-1] == v[0] and len(v) > 1 else ""
    return f"{m.group('k')}{q}{mark(kind)}{q}"


def _dsn(m: re.Match[str]) -> str:
    if m.group("pw") is None and not m.group("user"):
        return m.group(0)
    if m.group("pw") is None:  # user only, no password: keep, it is not a secret by itself
        return m.group(0)
    return f"{m.group('scheme')}{mark('dsn')}@"


def redact_text(text: str, known_secrets: Iterable[str] = ()) -> str:
    """Redact secrets from free text (logs, tracebacks, compose lines, HTTP bodies)."""
    for s in sorted({s for s in known_secrets if s and len(s) >= 4}, key=len, reverse=True):
        text = text.replace(s, mark("secret"))
    text = _DSN.sub(_dsn, text)
    text = _AUTH_HDR.sub(lambda m: f"{m.group('k')}{mark('authorization')}", text)
    text = _BEARER.sub(mark("authorization"), text)
    text = _PAIR.sub(_pair, text)
    for rx, kind in _SHAPES:
        text = rx.sub(mark(kind), text)
    return text


def redact_value(key: str, value: str, known_secrets: Iterable[str] = ()) -> str:
    """Redact a config value by key name first, then by content (DSN under any name)."""
    kind = secret_kind(key)
    if kind and value:
        return mark(kind)
    return redact_text(value, known_secrets)


def secret_values(env: dict[str, str]) -> set[str]:
    """Literal values of secret-like keys; later scrubbed from every text, wherever they appear."""
    out = {v for k, v in env.items() if secret_kind(k) and v and len(v) >= 4}
    for v in env.values():  # password inside a DSN-valued variable
        for m in _DSN.finditer(v):
            if m.group("pw"):
                out.add(m.group("pw"))
    return out
