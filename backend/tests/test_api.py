from pathlib import Path

import httpx
import pytest

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
async def test_ready_reports_loaded_documents(client: httpx.AsyncClient) -> None:
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "knowledge_documents": 1}


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
    assert response.json() == {"status": "not_ready", "knowledge_documents": 0}


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
    response = await client.post("/api/v1/chat", json={"question": "preferred Python tools?"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "extractive"
    assert "Python" in body["answer"]
    assert body["sources"][0]["path"] == "profile.md"


@pytest.mark.anyio
async def test_blank_and_unknown_fields_are_rejected(client: httpx.AsyncClient) -> None:
    blank = await client.post("/api/v1/chat", json={"question": "   "})
    extra = await client.post("/api/v1/chat", json={"question": "hello", "admin": True})
    assert blank.status_code == 422
    assert extra.status_code == 422
