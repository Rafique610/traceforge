"""Read-only showcase mode: refuse every state-changing request with 403."""

from typing import Any

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class ShowcaseReadOnlyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in SAFE_METHODS:
            response = JSONResponse({"detail": "Showcase mode is read-only."}, status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def add_showcase(app: Any, settings: Any) -> None:
    """Install the read-only guard when settings.showcase_mode is true."""
    if getattr(settings, "showcase_mode", False):
        app.add_middleware(ShowcaseReadOnlyMiddleware)
