import re
import threading
from pathlib import Path

import httpx
import pytest

import app.main as main_module
from app import __version__
from app.config import get_settings
from app.main import app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(tmp_path: Path):
    (tmp_path / "profile.md").write_text(
        "# Example profile\n\nThe agent prefers Python for data tools.", encoding="utf-8"
    )
    settings = get_settings()
    original = settings.knowledge_dir
    settings.knowledge_dir = str(tmp_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        yield value
    settings.knowledge_dir = original


@pytest.mark.anyio
async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.anyio
async def test_openapi_metadata_uses_project_brand_and_version(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    info = response.json()["info"]
    assert info["title"] == "Agent-Me API"
    assert info["version"] == __version__
    assert "AI Twin" in info["description"]


@pytest.mark.anyio
async def test_profile_exposes_public_runtime_configuration(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/profile")

    settings = get_settings()
    assert response.status_code == 200
    assert response.json() == {
        "name": settings.app_name,
        "description": settings.app_description,
        "max_question_chars": settings.max_question_chars,
        "external_provider_enabled": False,
    }


@pytest.mark.anyio
async def test_profile_discloses_external_provider_without_exposing_configuration(
    client: httpx.AsyncClient,
) -> None:
    settings = get_settings()
    originals = (settings.llm_base_url, settings.llm_api_key, settings.llm_model)
    settings.llm_base_url = "https://private-provider.example/v1"
    settings.llm_api_key = "private-api-key"
    settings.llm_model = "private-model"
    try:
        response = await client.get("/api/v1/profile")
    finally:
        settings.llm_base_url, settings.llm_api_key, settings.llm_model = originals

    assert response.status_code == 200
    assert response.json()["external_provider_enabled"] is True
    assert "private-provider" not in response.text
    assert "private-api-key" not in response.text
    assert "private-model" not in response.text


@pytest.mark.anyio
async def test_ready_reports_loaded_documents(client: httpx.AsyncClient) -> None:
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "knowledge_documents": 1,
        "answer_mode": "extractive",
    }


@pytest.mark.anyio
async def test_ready_fails_when_knowledge_directory_is_empty(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    settings = get_settings()
    original = settings.knowledge_dir
    settings.knowledge_dir = str(empty)
    try:
        response = await client.get("/ready")
    finally:
        settings.knowledge_dir = original

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "knowledge_documents": 0,
        "answer_mode": "extractive",
    }


@pytest.mark.anyio
async def test_unsafe_knowledge_returns_safe_service_error(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    (tmp_path / "oversized-private-name.md").write_text("too large", encoding="utf-8")
    settings = get_settings()
    original = settings.max_document_bytes
    settings.max_document_bytes = 2
    try:
        response = await client.get("/ready")
    finally:
        settings.max_document_bytes = original

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Knowledge base is temporarily unavailable.",
        "code": "knowledge_document_too_large",
    }
    assert "private-name" not in response.text


@pytest.mark.anyio
async def test_grounded_extractive_answer(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/chat", json={"question": "prefers Python tools?"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "extractive"
    assert "Python" in body["answer"]
    assert body["sources"][0]["path"] == "profile.md"


@pytest.mark.anyio
async def test_multi_agent_collaboration_returns_typed_trace(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/collaborate",
        json={"question": "prefers Python tools?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"].startswith("run_")
    assert body["workflow"] == "planner-researcher-critic-writer"
    assert body["mode"] == "multi-agent-local"
    assert body["grounded"] is True
    assert [stage["agent"] for stage in body["trace"]] == [
        "planner",
        "researcher",
        "critic",
        "writer",
    ]
    assert "[profile.md]" in body["answer"]
    assert body["sources"][0]["path"] == "profile.md"


@pytest.mark.anyio
async def test_verified_collaboration_returns_a_five_stage_trace(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/collaborate",
        json={"question": "prefers Python tools?", "workflow": "verified"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workflow"] == "planner-researcher-critic-writer-verifier"
    assert [stage["agent"] for stage in body["trace"]] == [
        "planner",
        "researcher",
        "critic",
        "writer",
        "verifier",
    ]
    assert body["trace"][-1]["metrics"]["approved"] is True


@pytest.mark.anyio
async def test_collaboration_rejects_an_unknown_workflow(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/collaborate",
        json={"question": "prefers Python tools?", "workflow": "attacker-controlled"},
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_knowledge_search_runs_outside_the_async_event_loop(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_loop_thread = threading.get_ident()
    search_threads: list[int] = []

    class RecordingKnowledgeBase:
        def search(self, question: str, *, limit: int = 4) -> list:
            search_threads.append(threading.get_ident())
            return []

    knowledge = RecordingKnowledgeBase()
    monkeypatch.setattr(main_module, "_knowledge_base", lambda *_: knowledge)

    chat = await client.post("/api/v1/chat", json={"question": "Unknown fact?"})
    collaboration = await client.post("/api/v1/collaborate", json={"question": "Unknown fact?"})

    assert chat.status_code == 200
    assert collaboration.status_code == 200
    assert len(search_threads) == 2
    assert all(thread != event_loop_thread for thread in search_threads)


@pytest.mark.anyio
async def test_multi_agent_request_is_strict_and_rejects_blank_questions(
    client: httpx.AsyncClient,
) -> None:
    blank = await client.post("/api/v1/collaborate", json={"question": "  "})
    extra = await client.post(
        "/api/v1/collaborate",
        json={"question": "Python?", "agent": "attacker-controlled"},
    )

    assert blank.status_code == 422
    assert extra.status_code == 422


@pytest.mark.anyio
async def test_blank_and_unknown_fields_are_rejected(client: httpx.AsyncClient) -> None:
    blank = await client.post("/api/v1/chat", json={"question": "   "})
    extra = await client.post("/api/v1/chat", json={"question": "hello", "admin": True})
    assert blank.status_code == 422
    assert extra.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("endpoint", ["/api/v1/chat", "/api/v1/collaborate"])
async def test_question_total_limit_has_a_stable_error_code(
    client: httpx.AsyncClient, endpoint: str
) -> None:
    settings = get_settings()
    original = settings.max_question_chars
    settings.max_question_chars = 5
    try:
        response = await client.post(endpoint, json={"question": "123456"})
    finally:
        settings.max_question_chars = original

    assert response.status_code == 413
    assert response.json()["code"] == "question_too_large"
    assert isinstance(response.json()["detail"], str)


@pytest.mark.anyio
async def test_history_total_limit_is_enforced(client: httpx.AsyncClient) -> None:
    settings = get_settings()
    original = settings.max_history_chars
    settings.max_history_chars = 5
    try:
        response = await client.post(
            "/api/v1/chat",
            json={
                "question": "Python?",
                "history": [{"role": "user", "content": "123456"}],
            },
        )
    finally:
        settings.max_history_chars = original

    assert response.status_code == 413
    assert response.json()["code"] == "history_too_large"
    assert isinstance(response.json()["detail"], str)


@pytest.mark.anyio
async def test_declared_oversized_request_body_is_rejected_before_parsing(
    client: httpx.AsyncClient,
) -> None:
    settings = get_settings()
    original = settings.max_request_body_bytes
    settings.max_request_body_bytes = 1_024
    try:
        response = await client.post("/api/v1/chat", json={"question": "x" * 2_048})
    finally:
        settings.max_request_body_bytes = original

    assert response.status_code == 413
    assert response.json() == {
        "detail": "request body exceeds configured limit",
        "code": "request_body_too_large",
    }


@pytest.mark.anyio
async def test_streamed_oversized_request_body_is_rejected(
    client: httpx.AsyncClient,
) -> None:
    async def chunks():
        yield b'{"question":"'
        yield b"x" * 2_048
        yield b'"}'

    settings = get_settings()
    original = settings.max_request_body_bytes
    settings.max_request_body_bytes = 1_024
    try:
        response = await client.post(
            "/api/v1/chat",
            content=chunks(),
            headers={"Content-Type": "application/json"},
        )
    finally:
        settings.max_request_body_bytes = original

    assert response.status_code == 413
    assert response.json()["code"] == "request_body_too_large"


@pytest.mark.anyio
async def test_incomplete_provider_configuration_fails_explicitly(
    client: httpx.AsyncClient,
) -> None:
    settings = get_settings()
    original = (settings.llm_base_url, settings.llm_api_key, settings.llm_model)
    settings.llm_base_url = "https://provider.example/v1"
    settings.llm_api_key = ""
    settings.llm_model = ""
    try:
        readiness = await client.get("/ready")
        response = await client.post("/api/v1/chat", json={"question": "Python?"})
    finally:
        settings.llm_base_url, settings.llm_api_key, settings.llm_model = original

    assert readiness.status_code == 503
    assert readiness.json()["answer_mode"] == "misconfigured"
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Provider configuration is incomplete.",
        "code": "provider_configuration_incomplete",
    }


REQUEST_ID_PATTERN = re.compile(r"^req_[0-9a-f]{32}$")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("get", "/health", {}),
        ("get", "/api/v1/profile", {}),
        ("post", "/api/v1/chat", {"json": {"question": "prefers Python tools?"}}),
    ],
)
async def test_request_id_header_present_on_success(
    client: httpx.AsyncClient, method: str, path: str, kwargs: dict
) -> None:
    response = await client.request(method, path, **kwargs)

    assert response.status_code == 200
    assert REQUEST_ID_PATTERN.match(response.headers["x-request-id"])


@pytest.mark.anyio
async def test_request_id_header_present_on_handled_errors(client: httpx.AsyncClient) -> None:
    validation_error = await client.post(
        "/api/v1/collaborate",
        json={"question": "prefers Python tools?", "workflow": "attacker-controlled"},
    )

    settings = get_settings()
    original = settings.max_question_chars
    settings.max_question_chars = 5
    try:
        semantic_limit_error = await client.post("/api/v1/chat", json={"question": "123456"})
    finally:
        settings.max_question_chars = original

    assert validation_error.status_code == 422
    assert REQUEST_ID_PATTERN.match(validation_error.headers["x-request-id"])
    assert semantic_limit_error.status_code == 413
    assert REQUEST_ID_PATTERN.match(semantic_limit_error.headers["x-request-id"])


@pytest.mark.anyio
async def test_request_id_is_fresh_and_ignores_client_supplied_value(
    client: httpx.AsyncClient,
) -> None:
    spoofed = "req_" + "a" * 32
    first = await client.get("/health", headers={"X-Request-ID": spoofed})
    second = await client.get("/health", headers={"X-Request-ID": spoofed})

    assert first.headers["x-request-id"] != spoofed
    assert second.headers["x-request-id"] != spoofed
    assert first.headers["x-request-id"] != second.headers["x-request-id"]


@pytest.mark.anyio
async def test_request_id_header_is_exposed_to_allowed_browser_origins(
    client: httpx.AsyncClient,
) -> None:
    origin = get_settings().allowed_origins[0]
    response = await client.get("/health", headers={"Origin": origin})

    exposed = response.headers.get("access-control-expose-headers", "")
    assert "X-Request-ID" in exposed
    assert response.headers["access-control-allow-origin"] == origin
