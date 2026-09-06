from pathlib import Path

import httpx
import pytest

from app.config import Settings, get_settings
from app.main import app
from app.personal import Entry, Store


@pytest.fixture
async def personal(tmp_path):
    knowledge = tmp_path / "public"
    knowledge.mkdir()
    config = Settings(
        _env_file=None,
        personal_enabled=True,
        personal_token="t" * 40,
        personal_data_dir=str(tmp_path / "private"),
        knowledge_dir=str(knowledge),
    )
    app.dependency_overrides[get_settings] = lambda: config
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, config
    app.dependency_overrides.clear()


HEADERS = {"Authorization": "Bearer " + "t" * 40}


async def test_auth_and_disabled(personal):
    client, config = personal
    for path in ("entries", "history", "export"):
        assert (await client.get(f"/api/v1/personal/{path}")).status_code == 401
    assert not Path(config.personal_data_dir).exists()  # noqa: ASYNC240
    config.personal_enabled = False
    assert (await client.get("/api/v1/personal/entries", headers=HEADERS)).status_code == 404


async def test_confirm_edit_delete_and_public_isolation(personal):
    client, config = personal
    base = "/api/v1/personal"
    response = await client.post(
        base + "/entries",
        headers=HEADERS,
        json={"kind": "fact", "key": "project", "content": "SecretOrchid"},
    )
    item = response.json()
    assert item["status"] == "pending"
    query = {"question": "SecretOrchid"}
    assert not (await client.post(base + "/chat", json=query, headers=HEADERS)).json()["sources"]
    await client.post(base + f"/entries/{item['id']}/confirm", headers=HEADERS, json={})
    assert (
        "SecretOrchid"
        in (await client.post(base + "/chat", json=query, headers=HEADERS)).json()["answer"]
    )
    assert not (await client.post("/api/v1/chat", json=query)).json()["sources"]
    # A new Store instance sees persisted confirmed data.
    assert Store(config.personal_data_dir).entries()[0]["status"] == "confirmed"
    await client.post(
        base + f"/entries/{item['id']}/edit",
        headers=HEADERS,
        json={"kind": "fact", "key": "project", "content": "NewOrchid"},
    )
    assert not (await client.post(base + "/chat", json=query, headers=HEADERS)).json()["sources"]
    await client.post(base + f"/entries/{item['id']}/confirm", headers=HEADERS, json={})
    await client.post(base + f"/entries/{item['id']}/delete", headers=HEADERS, json={})
    assert not (await client.post(base + "/chat", json=query, headers=HEADERS)).json()["sources"]
    exported = (await client.get(base + "/export", headers=HEADERS)).json()
    assert exported["entries"] == [] and exported["history"]
    await client.post(base + "/history/clear", headers=HEADERS, json={})
    assert (await client.get(base + "/history", headers=HEADERS)).json() == []


async def test_candidate_and_explicit_conflict(personal):
    client, _ = personal
    base = "/api/v1/personal"
    await client.post(base + "/chat", headers=HEADERS, json={"question": "记住：先给结论"})
    items = (await client.get(base + "/entries", headers=HEADERS)).json()
    first = items[0]
    assert first["content"] == "先给结论" and first["source"].startswith("turn:")
    await client.post(base + f"/entries/{first['id']}/confirm", headers=HEADERS, json={})
    await client.post(base + "/chat", headers=HEADERS, json={"question": "记住：先给细节"})
    second = (await client.get(base + "/entries", headers=HEADERS)).json()[1]
    url = base + f"/entries/{second['id']}/confirm"
    assert (await client.post(url, headers=HEADERS, json={})).status_code == 409
    assert (
        await client.post(url, headers=HEADERS, json={"replace_ids": ["wrong"]})
    ).status_code == 409
    assert (
        await client.post(url, headers=HEADERS, json={"replace_ids": [first["id"]]})
    ).status_code == 200
    assert len((await client.get(base + "/entries", headers=HEADERS)).json()) == 1


async def test_private_markdown_and_validation(personal):
    client, config = personal
    root = Path(config.personal_data_dir) / "knowledge"
    root.mkdir(parents=True)
    (root / "local.md").write_text("# Private\n\nSecretTulip", encoding="utf-8")
    result = await client.post(
        "/api/v1/personal/chat", headers=HEADERS, json={"question": "SecretTulip"}
    )
    assert result.json()["sources"][0]["path"].startswith("private/knowledge/")
    assert not (await client.post("/api/v1/chat", json={"question": "SecretTulip"})).json()[
        "sources"
    ]
    assert (
        await client.post(
            "/api/v1/personal/entries", headers=HEADERS, json={"key": " ", "content": "x"}
        )
    ).status_code == 422


def test_preferences_survive_and_deleted_not_retrieved(tmp_path):
    db = Store(str(tmp_path))
    item = db.add(Entry(kind="preference", key="response.style", content="Be concise"))
    assert db.context("unrelated") == []
    db.confirm(item["id"], [])
    assert Store(str(tmp_path)).context("unrelated")
    db.delete(item["id"])
    assert not db.context("unrelated")


async def test_private_provider_receives_only_current_confirmed_context(personal, monkeypatch):
    import app.personal as personal_module

    client, config = personal
    captured = []

    async def fake_answer(**kwargs):
        captured.append(kwargs)
        return "Generated answer", "openai-compatible"

    monkeypatch.setattr(personal_module, "generate_answer", fake_answer)
    db = Store(config.personal_data_dir)
    pending = db.add(Entry(kind="fact", key="private.fact", content="PendingSecret"))
    approved = db.add(Entry(kind="preference", key="response.style", content="Short paragraphs"))
    db.confirm(approved["id"], [])
    db.save_chat("OldSecret", "Old answer")
    response = await client.post(
        "/api/v1/personal/chat", headers=HEADERS, json={"question": "PendingSecret"}
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    context = "\n".join(m.excerpt for m in captured[0]["matches"])
    assert "Short paragraphs" in context
    assert "PendingSecret" not in context
    assert "OldSecret" not in context
    assert captured[0]["history"] == []
    db.delete(pending["id"])
    db.delete(approved["id"])
    await client.post("/api/v1/personal/chat", headers=HEADERS, json={"question": "paragraphs"})
    assert not captured[-1]["matches"]
