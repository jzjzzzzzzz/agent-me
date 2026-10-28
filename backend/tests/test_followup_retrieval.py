"""A follow-up must retrieve its referent before asking the answer model."""

import json

import httpx
import pytest

from app import provider
from app.config import Settings, get_settings
from app.main import app


@pytest.mark.anyio
@pytest.mark.parametrize("long_neighbor", [False, True])
@pytest.mark.parametrize(
    ("first_question", "followup", "document"),
    [
        (
            "Which tool do I use for paper figures?",
            "Why did I choose it?",
            "I use Matplotlib as my tool for paper figures. I choose Matplotlib because "
            "its Python scripts make my paper figures reproducible.",
        ),
        (
            "论文画图工具？",
            "为什么选它？",
            "论文画图工具是Matplotlib。选择Matplotlib的原因是Python脚本便于复现。",
        ),
    ],
)
async def test_chat_followup_retrieves_grounding_and_keeps_original_question(
    tmp_path, monkeypatch, first_question, followup, document, long_neighbor
):
    text = "My figures archive: " + "gardening " * 700 + "\n\n" if long_neighbor else ""
    (tmp_path / "figures.md").write_text(text + document, encoding="utf-8")
    settings = Settings(
        _env_file=None,
        knowledge_dir=str(tmp_path),
        llm_base_url="https://provider.example/v1",
        llm_api_key="synthetic-key",
        llm_model="synthetic-model",
    )
    history = [
        {"role": "user", "content": first_question},
        {"role": "assistant", "content": "Matplotlib. [figures.md]"},
    ]
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        content = "Python scripts make paper figures reproducible. [figures.md]"
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    original_client = httpx.AsyncClient

    def upstream_client(**kwargs):
        return original_client(**{**kwargs, "transport": httpx.MockTransport(handler)})

    app.dependency_overrides[get_settings] = lambda: settings
    try:
        async with original_client(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            monkeypatch.setattr(provider.httpx, "AsyncClient", upstream_client)
            response = await client.post(
                "/api/v1/chat",
                json={
                    "question": followup,
                    "history": history,
                    "previous_sources": [{"path": "figures.md", "excerpt": document}],
                },
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert [source["path"] for source in response.json()["sources"]] == ["figures.md"]
    assert len(calls) == 1
    final_messages = calls[-1]["messages"]
    assert document in final_messages[0]["content"]
    assert final_messages[-1] == {"role": "user", "content": followup}
    assert final_messages[1:-1] == history


@pytest.mark.anyio
@pytest.mark.parametrize(
    "sources",
    [
        [{"path": "figures.md", "excerpt": " "}],
        [{"path": "figures.md", "excerpt": "x" * 4001}],
        [{"path": "figures.md", "excerpt": "example", "score": 1}],
        [{"path": "figures.md", "excerpt": "example"}] * 5,
    ],
)
async def test_invalid_source_locators_are_rejected_before_retrieval(sources, monkeypatch):
    from app import main as main_module

    def forbidden(*args):
        pytest.fail("Invalid locators must be rejected before knowledge or provider work")

    monkeypatch.setattr(main_module, "retrieve_chat_context", forbidden)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/chat", json={"question": "Why?", "previous_sources": sources}
        )
    assert response.status_code == 422
