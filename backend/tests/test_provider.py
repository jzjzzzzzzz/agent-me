import json
import traceback
from collections.abc import Awaitable, Callable

import httpx
import pytest

from app.config import Settings
from app.provider import ProviderError, generate_answer
from app.schemas import ChatTurn
from app.semantic_learning import INSTRUCTIONS, propose

Completion = Callable[[Settings, httpx.AsyncBaseTransport], Awaitable[str]]


@pytest.fixture(params=["answer", "semantic"])
def complete(request: pytest.FixtureRequest) -> Completion:
    async def call(settings: Settings, transport: httpx.AsyncBaseTransport) -> str:
        if request.param == "semantic":
            return await propose(settings, "Question", transport)
        answer, mode = await generate_answer(
            question="Question", history=[], matches=[], settings=settings, transport=transport
        )
        assert mode == "openai-compatible"
        return answer

    return call


class CountingStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.yielded = 0
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            self.yielded += 1
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


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
        assert request.method == "POST"
        assert request.url == "https://provider.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer secret-value"
        assert request.extensions["timeout"] == dict.fromkeys(
            ["connect", "read", "write", "pool"], 7.5
        )
        payload = json.loads(request.content)
        assert payload["model"] == "example-model"
        assert payload["stream"] is False
        assert payload["messages"][0]["role"] == "system"
        assert "Answer only from the supplied context." in payload["messages"][0]["content"]
        assert payload["messages"][1:] == [
            {"role": "user", "content": "Earlier question"},
            {"role": "assistant", "content": "Earlier answer"},
            {"role": "user", "content": "Question"},
        ]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Grounded answer"}}]},
        )

    answer, mode = await generate_answer(
        question="Question",
        history=[
            ChatTurn(role="user", content="Earlier question"),
            ChatTurn(role="assistant", content="Earlier answer"),
        ],
        matches=[],
        settings=provider_settings(
            llm_base_url="https://provider.example/v1/", provider_timeout_seconds=7.5
        ),
        transport=httpx.MockTransport(handler),
    )

    assert answer == "Grounded answer"
    assert mode == "openai-compatible"


@pytest.mark.anyio
async def test_semantic_request_contains_only_fixed_instructions_and_exact_source() -> None:
    source = "  Exact consented source.\nDo not normalize this text.\n"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://provider.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer secret-value"
        assert request.extensions["timeout"] == dict.fromkeys(
            ["connect", "read", "write", "pool"], 7.5
        )
        assert json.loads(request.content) == {
            "model": "example-model",
            "stream": False,
            "messages": [
                {"role": "system", "content": INSTRUCTIONS},
                {"role": "user", "content": source},
            ],
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": "Result"}}]})

    assert (
        await propose(
            provider_settings(
                llm_base_url="https://provider.example/v1/", provider_timeout_seconds=7.5
            ),
            source,
            httpx.MockTransport(handler),
        )
        == "Result"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "expected_code"),
    [
        (httpx.Response(200, json={"choices": []}), "provider_response_invalid"),
        (httpx.Response(200, content=b"not-json"), "provider_response_invalid"),
        (
            httpx.Response(200, json={"choices": [{"message": {"content": " "}}]}),
            "provider_response_invalid",
        ),
        (
            httpx.Response(200, json={"choices": [{"message": {"content": 123}}]}),
            "provider_response_invalid",
        ),
        (
            httpx.Response(302, headers={"Location": "https://other.example"}),
            "provider_request_failed",
        ),
        (httpx.Response(401, text="private-provider-error-content"), "provider_request_failed"),
        (httpx.Response(429, json={"error": "slow down"}), "provider_rate_limited"),
        (httpx.Response(500, text="private-provider-error-content"), "provider_request_failed"),
    ],
)
async def test_provider_failures_are_classified_safely(
    complete: Completion, response: httpx.Response, expected_code: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        response.request = request
        return response

    with pytest.raises(ProviderError) as captured:
        await complete(
            settings=provider_settings(),
            transport=httpx.MockTransport(handler),
        )

    assert captured.value.code == expected_code
    assert captured.value.status_code == 502
    assert "secret-value" not in str(captured.value)
    assert "private-provider-error-content" not in "".join(
        traceback.format_exception(captured.value)
    )
    assert response.is_closed


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("failure", "expected_code"),
    [
        (httpx.ConnectTimeout, "provider_timeout"),
        (httpx.ReadTimeout, "provider_timeout"),
        (httpx.ConnectError, "provider_unavailable"),
    ],
)
async def test_transport_failures_are_classified_without_leaking_details(
    complete: Completion, failure: type[httpx.RequestError], expected_code: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise failure("upstream internal detail secret-value", request=request)

    with pytest.raises(ProviderError) as captured:
        await complete(
            settings=provider_settings(),
            transport=httpx.MockTransport(handler),
        )

    assert captured.value.code == expected_code
    assert captured.value.status_code == 502
    formatted = "".join(traceback.format_exception(captured.value))
    assert "upstream internal detail" not in formatted
    assert "secret-value" not in formatted


@pytest.mark.anyio
async def test_provider_answer_size_limit_is_enforced(complete: Completion) -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json={"choices": [{"message": {"content": "too long"}}]},
        )
    )

    with pytest.raises(ProviderError) as captured:
        await complete(
            settings=provider_settings(max_answer_chars=3),
            transport=transport,
        )

    assert captured.value.code == "provider_response_too_large"


@pytest.mark.anyio
async def test_declared_oversized_provider_response_is_rejected_before_reading(
    complete: Completion,
) -> None:
    stream = CountingStream([b"must not be read"])
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            headers={"Content-Length": "2048"},
            stream=stream,
        )
    )

    with pytest.raises(ProviderError) as captured:
        await complete(
            settings=provider_settings(max_provider_response_bytes=1024),
            transport=transport,
        )

    assert captured.value.code == "provider_response_too_large"
    assert stream.yielded == 0
    assert stream.closed


@pytest.mark.anyio
@pytest.mark.parametrize("declared_length", [None, "invalid", "512"])
async def test_chunked_oversized_provider_response_stops_at_the_limit(
    complete: Completion, declared_length: str | None
) -> None:
    stream = CountingStream([b"x" * 700, b"y" * 400, b"must not be read"])
    headers = {} if declared_length is None else {"Content-Length": declared_length}
    transport = httpx.MockTransport(lambda _: httpx.Response(200, headers=headers, stream=stream))

    with pytest.raises(ProviderError) as captured:
        await complete(
            settings=provider_settings(max_provider_response_bytes=1024),
            transport=transport,
        )

    assert captured.value.code == "provider_response_too_large"
    assert stream.yielded == 2
    assert stream.closed


@pytest.mark.anyio
async def test_provider_response_exactly_at_byte_limit_is_parsed(complete: Completion) -> None:
    body = json.dumps(
        {"choices": [{"message": {"content": "Boundary answer"}}]},
        separators=(",", ":"),
    ).encode()
    padding = b" " * (1024 - len(body))
    response_body = body + padding
    stream = CountingStream([response_body[:512], response_body[512:]])
    transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=stream))

    answer = await complete(
        settings=provider_settings(max_provider_response_bytes=len(response_body)),
        transport=transport,
    )

    assert answer == "Boundary answer"
    assert stream.yielded == 2
    assert stream.closed


@pytest.mark.anyio
async def test_provider_stream_failure_is_classified_and_closed(complete: Completion) -> None:
    class FailingStream(CountingStream):
        async def __aiter__(self):
            yield b"partial response"
            raise httpx.ReadError("private-stream-error-content")

    stream = FailingStream([])
    transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=stream))

    with pytest.raises(ProviderError) as captured:
        await complete(settings=provider_settings(), transport=transport)

    assert captured.value.code == "provider_unavailable"
    assert "private-stream-error-content" not in "".join(traceback.format_exception(captured.value))
    assert stream.closed
