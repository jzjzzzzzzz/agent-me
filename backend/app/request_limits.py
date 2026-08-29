from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import Settings


class RequestBodyLimitMiddleware:
    """Reject oversized HTTP bodies before route-level JSON parsing.

    Content-Length permits an immediate rejection. Bounded buffering also
    covers chunked requests and clients that omit the header.
    """

    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        max_bytes = self.settings.max_request_body_bytes
        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > max_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                # The application server or route parser will handle a malformed header.
                pass

        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > max_bytes:
                await self._reject(scope, receive, send)
                return
            more_body = message.get("more_body", False)

        delivered = False

        async def limited_receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, limited_receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=413,
            content={
                "detail": "request body exceeds configured limit",
                "code": "request_body_too_large",
            },
        )
        await response(scope, receive, send)
