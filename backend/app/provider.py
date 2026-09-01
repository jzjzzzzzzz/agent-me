from __future__ import annotations

import json

import httpx

from .config import Settings
from .knowledge import Match
from .schemas import ChatTurn


class ProviderError(RuntimeError):
    """A safe, classified failure from provider configuration or execution."""

    def __init__(self, code: str, *, status_code: int = 502) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)


def extractive_answer(matches: list[Match]) -> str:
    if not matches:
        return "I could not find a grounded answer in the configured knowledge files."
    return matches[0].excerpt


def _answer_content(response_body: bytes, max_answer_chars: int) -> str:
    try:
        data = json.loads(response_body)
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise ProviderError("provider_response_invalid") from error
    if not isinstance(content, str) or not content.strip():
        raise ProviderError("provider_response_invalid")
    if len(content) > max_answer_chars:
        raise ProviderError("provider_response_too_large")
    return content


async def _read_limited_response(response: httpx.Response, max_bytes: int) -> bytes:
    declared_length = response.headers.get("content-length")
    if declared_length is not None:
        try:
            if int(declared_length) > max_bytes:
                raise ProviderError("provider_response_too_large")
        except ValueError:
            # An invalid length is not trusted; the streamed byte count remains authoritative.
            pass

    body = bytearray()
    async for chunk in response.aiter_bytes():
        if len(body) + len(chunk) > max_bytes:
            raise ProviderError("provider_response_too_large")
        body.extend(chunk)
    return bytes(body)


async def generate_answer(
    *,
    question: str,
    history: list[ChatTurn],
    matches: list[Match],
    settings: Settings,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[str, str]:
    if settings.provider_state == "extractive":
        return extractive_answer(matches), "extractive"
    if settings.provider_state == "misconfigured":
        raise ProviderError("provider_configuration_incomplete", status_code=503)

    context = "\n\n".join(f"Source: {match.document.path}\n{match.excerpt}" for match in matches)[
        : settings.max_context_chars
    ]
    system = (
        "Answer only from the supplied context. If the context is insufficient, say so. "
        "Do not invent personal facts. Cite source paths in brackets.\n\nContext:\n" + context
    )
    messages = [{"role": "system", "content": system}]
    messages.extend(turn.model_dump() for turn in history)
    messages.append({"role": "user", "content": question})

    endpoint = settings.llm_base_url.rstrip("/") + "/chat/completions"
    try:
        async with httpx.AsyncClient(
            timeout=settings.provider_timeout_seconds,
            transport=transport,
        ) as client:
            async with client.stream(
                "POST",
                endpoint,
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={"model": settings.llm_model, "messages": messages, "stream": False},
            ) as response:
                response.raise_for_status()
                response_body = await _read_limited_response(
                    response,
                    settings.max_provider_response_bytes,
                )
    except httpx.TimeoutException as error:
        raise ProviderError("provider_timeout") from error
    except httpx.HTTPStatusError as error:
        code = (
            "provider_rate_limited"
            if error.response.status_code == 429
            else "provider_request_failed"
        )
        raise ProviderError(code) from error
    except httpx.RequestError as error:
        raise ProviderError("provider_unavailable") from error

    return _answer_content(response_body, settings.max_answer_chars), "openai-compatible"
