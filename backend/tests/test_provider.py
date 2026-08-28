import httpx
import pytest

from app.config import Settings
from app.provider import ProviderError, generate_answer


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
