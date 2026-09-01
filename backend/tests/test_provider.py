import json

import httpx
import pytest

from app.config import Settings
from app.provider import ProviderError, generate_answer


class CountingStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.yielded = 0

    async def __aiter__(self):
        for chunk in self.chunks:
            self.yielded += 1
            yield chunk


def provider_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "llm_base_url": "https://provider.example/v1",
        "llm_api_key": "secret-value",
        "llm_model": "example-model",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.anyio
async def test_provider_request_is_grounded_and_response_is_validated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://provider.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer secret-value"
        payload = __import__("json").loads(request.content)
        assert payload["stream"] is False
        assert payload["messages"][0]["role"] == "system"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Grounded answer"}}]},
        )

    answer, mode = await generate_answer(
        question="Question",
        history=[],
        matches=[],
        settings=provider_settings(),
        transport=httpx.MockTransport(handler),
    )

    assert answer == "Grounded answer"
    assert mode == "openai-compatible"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "expected_code"),
    [
        (httpx.Response(200, json={"choices": []}), "provider_response_invalid"),
        (httpx.Response(200, content=b"not-json"), "provider_response_invalid"),
        (httpx.Response(429, json={"error": "slow down"}), "provider_rate_limited"),
    ],
)
async def test_provider_failures_are_classified_safely(
    response: httpx.Response, expected_code: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        response.request = request
        return response

    with pytest.raises(ProviderError) as captured:
        await generate_answer(
            question="Question",
            history=[],
            matches=[],
            settings=provider_settings(),
            transport=httpx.MockTransport(handler),
        )

    assert captured.value.code == expected_code
    assert "secret-value" not in str(captured.value)


@pytest.mark.anyio
async def test_provider_timeout_is_classified_without_leaking_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream internal detail", request=request)

    with pytest.raises(ProviderError) as captured:
        await generate_answer(
            question="Question",
            history=[],
            matches=[],
            settings=provider_settings(),
            transport=httpx.MockTransport(handler),
        )

    assert captured.value.code == "provider_timeout"
    assert "upstream internal detail" not in str(captured.value)


@pytest.mark.anyio
async def test_provider_answer_size_limit_is_enforced() -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json={"choices": [{"message": {"content": "too long"}}]},
        )
    )

    with pytest.raises(ProviderError) as captured:
        await generate_answer(
            question="Question",
            history=[],
            matches=[],
            settings=provider_settings(max_answer_chars=3),
            transport=transport,
        )

    assert captured.value.code == "provider_response_too_large"


@pytest.mark.anyio
async def test_declared_oversized_provider_response_is_rejected_before_reading() -> None:
    stream = CountingStream([b"must not be read"])
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            headers={"Content-Length": "2048"},
            stream=stream,
        )
    )

    with pytest.raises(ProviderError) as captured:
        await generate_answer(
            question="Question",
            history=[],
            matches=[],
            settings=provider_settings(max_provider_response_bytes=1024),
            transport=transport,
        )

    assert captured.value.code == "provider_response_too_large"
    assert stream.yielded == 0


@pytest.mark.anyio
async def test_chunked_oversized_provider_response_stops_at_the_limit() -> None:
    stream = CountingStream([b"x" * 700, b"y" * 400, b"must not be read"])
    transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=stream))

    with pytest.raises(ProviderError) as captured:
        await generate_answer(
            question="Question",
            history=[],
            matches=[],
            settings=provider_settings(max_provider_response_bytes=1024),
            transport=transport,
        )

    assert captured.value.code == "provider_response_too_large"
    assert stream.yielded == 2


@pytest.mark.anyio
async def test_provider_response_exactly_at_byte_limit_is_parsed() -> None:
    body = json.dumps(
        {"choices": [{"message": {"content": "Boundary answer"}}]},
        separators=(",", ":"),
    ).encode()
    padding = b" " * (1024 - len(body))
    response_body = body + padding
    stream = CountingStream([response_body[:512], response_body[512:]])
    transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=stream))

    answer, mode = await generate_answer(
        question="Question",
        history=[],
        matches=[],
        settings=provider_settings(max_provider_response_bytes=len(response_body)),
        transport=transport,
    )

    assert answer == "Boundary answer"
    assert mode == "openai-compatible"
    assert stream.yielded == 2
