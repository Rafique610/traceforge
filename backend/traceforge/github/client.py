"""Strict issue-URL parser and a read-only GitHub REST client (stdlib urllib, no redirects)."""

import json
import re
import urllib.error
import urllib.request
from typing import Any

from traceforge.config import Settings

MAX_BYTES = 1_000_000
_URL = re.compile(
    r"https://github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))"
    r"/([A-Za-z0-9._-]{1,100})/issues/([1-9][0-9]{0,8})"
)


class GitHubError(Exception):
    """Mapped to an HTTP status by the router. Messages never contain the token."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def parse_issue_url(url: str) -> tuple[str, str, int]:
    m = _URL.fullmatch(url) if isinstance(url, str) else None
    if not m or m.group(2) in {".", ".."}:
        raise GitHubError(422, "url must be https://github.com/<owner>/<repo>/issues/<number>")
    return m.group(1), m.group(2), int(m.group(3))


def is_allowed(owner: str, repo: str, allowed: list[str]) -> bool:
    entries = {a.strip().lower() for a in allowed if a.strip()}
    return f"{owner}/{repo}".lower() in entries or owner.lower() in entries


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any):
        return None


def _open(req: urllib.request.Request, timeout: float) -> tuple[int, dict[str, str], bytes]:
    """The only network call; tests replace it."""
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(req, timeout=timeout) as resp:
        return resp.status, dict(resp.headers), resp.read(MAX_BYTES + 1)


def fetch_issue(owner: str, repo: str, number: int, settings: Settings) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "traceforge-intake",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token.get_secret_value()}"
    base = settings.github_api_base.rstrip("/")
    req = urllib.request.Request(f"{base}/repos/{owner}/{repo}/issues/{number}", headers=headers)
    try:
        status, _, body = _open(req, settings.github_timeout_s)
    except urllib.error.HTTPError as e:
        hdrs = {k.lower(): v for k, v in e.headers.items()} if e.headers else {}
        if e.code == 404:
            raise GitHubError(404, "GitHub issue not found (or repository is private)") from None
        if e.code == 429 or (e.code == 403 and hdrs.get("x-ratelimit-remaining") == "0"):
            raise GitHubError(
                502, "GitHub rate limit exceeded; retry later or set a token"
            ) from None
        raise GitHubError(502, f"GitHub request failed with HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise GitHubError(502, "GitHub is unreachable (network error or timeout)") from None
    if status != 200 or len(body) > MAX_BYTES:
        raise GitHubError(502, "unexpected GitHub response (status or size)")
    try:
        data = json.loads(body)
    except ValueError:
        raise GitHubError(502, "GitHub returned invalid JSON") from None
    if not isinstance(data, dict):
        raise GitHubError(502, "GitHub returned an unexpected payload")
    return data
