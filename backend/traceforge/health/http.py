"""HTTP hygiene: request ids, structured access log, body size limit, generic 500."""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger("traceforge.http")
REQUEST_ID = "x-request-id"


class _TooLarge(Exception):
    pass


class RequestHygieneMiddleware:
    """Pure ASGI: assigns/echoes a request id, caps request bodies, logs one line per request.

    Only the method, path (no query string), status and duration are logged, never bodies
    or headers, so secrets cannot leak through the access log.
    """

    def __init__(self, app: ASGIApp, max_body_bytes: int = 1_000_000) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        incoming = headers.get(REQUEST_ID.encode(), b"").decode("latin-1")[:64]
        rid = incoming if incoming.isalnum() or incoming.replace("-", "").isalnum() else ""
        rid = rid or uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = rid
        started = time.perf_counter()
        status = 0
        began = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status, began
            if message["type"] == "http.response.start":
                status, began = message["status"], True
                message.setdefault("headers", []).append((REQUEST_ID.encode(), rid.encode()))
            await send(message)

        declared = headers.get(b"content-length", b"0")
        if declared.isdigit() and int(declared) > self.max_body_bytes:
            await self._too_large(scope, receive, send_wrapper)
            status = 413
        else:
            seen = 0

            async def receive_wrapper() -> Message:
                nonlocal seen
                message = await receive()
                if message["type"] == "http.request":
                    seen += len(message.get("body", b""))
                    if seen > self.max_body_bytes:
                        raise _TooLarge
                return message

            try:
                await self.app(scope, receive_wrapper, send_wrapper)
            except _TooLarge:
                if not began:
                    await self._too_large(scope, receive, send_wrapper)
                    status = 413
        log.info(
            "request",
            extra={
                "request_id": rid,
                "method": scope["method"],
                "path": scope["path"],
                "status": status,
                "ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )

    async def _too_large(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse({"detail": "request body too large"}, status_code=413)
        await response(scope, receive, send)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, "request_id", None)
        log.error(
            "unhandled error", extra={"request_id": rid, "path": request.url.path}, exc_info=exc
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "internal server error", "request_id": rid},
            headers={REQUEST_ID: rid or ""},
        )
