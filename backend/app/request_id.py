from __future__ import annotations

import secrets

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = b"x-request-id"
REQUEST_ID_PREFIX = "req_"


def generate_request_id() -> str:
    """Return a fresh, collision-resistant, server-controlled request ID."""
    return f"{REQUEST_ID_PREFIX}{secrets.token_hex(16)}"


class RequestIDMiddleware:
    """Attach a server-generated `X-Request-ID` to every HTTP response.

    Any client-supplied `X-Request-ID` request header is ignored: it is
    never read, trusted, or reflected back.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = generate_request_id()

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER, request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_request_id)
