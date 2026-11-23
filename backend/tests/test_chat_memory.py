from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.chat_memory import propose
from app.disclosure import DisclosureManager, target_id
from app.identity import IdentityStore
from app.memory import Store
from app.memory_models import EntityInput, Entry
from app.owner_models import DisclosurePolicy

BASE = "/api/v1/personal"
HEADERS = {"Authorization": "Bearer " + "t" * 40}


async def api(client, path, payload=None):
    if payload is None:
        response = await client.get(BASE + path, headers=HEADERS)
    else:
        response = await client.post(BASE + path, json=payload, headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def register_project(store, name, sensitivity="private"):
    identity = IdentityStore(store)
    project = identity.add(EntityInput(kind="project", name=name, sensitivity=sensitivity))
    identity.confirm(project["id"], project["revision"])
    return project["id"]


def confirm(store, key, content, *, entity_id=None, kind="preference", **time):
    entry = store.add(Entry(kind=kind, key=key, content=content, entity_id=entity_id, **time))
    store.confirm(entry["id"], [], entry["revision"])
    return entry["id"]


async def test_cross_session_preference_capture_replace_and_forget(personal):
    client, config = personal
    saved = await api(
        client,
        "/chat",
        {"question": "记住：偏好 response.style = Orchid updates lead with results"},
    )
    first = saved["capture"]
    assert saved["mode"] == "memory-review" and first["outcome"] == "created"
    assert not (await api(client, "/chat", {"question": "Orchid updates"}))["sources"]

    # A fresh DB handle (no shared request/session state) sees the reviewed memory.
    db = Store(config.personal_data_dir)
    db.confirm(first["memory_id"], [], 1)
    assert (
        "lead with results"
        in (await api(client, "/chat", {"question": "Orchid updates"}))["answer"]
    )
    repeated = await api(
        client,
        "/chat",
        {"question": "Remember: preference response.style = Orchid updates lead with results"},
    )
    assert repeated["capture"]["outcome"] == "existing"
    assert repeated["capture"]["memory_id"] == first["memory_id"]

    replacement = (
        await api(
            client,
            "/chat",
            {"question": "更正：偏好 response.style = Orchid updates lead with risks"},
        )
    )["capture"]["memory_id"]
    assert "results" in (await api(client, "/chat", {"question": "Orchid updates"}))["answer"]
    conflict = await client.post(BASE + f"/entries/{replacement}/confirm", headers=HEADERS, json={})
    assert conflict.status_code == 409
    await api(
        client,
        f"/entries/{replacement}/confirm",
        {
            "expected_revision": 1,
            "replace_ids": [first["memory_id"]],
            "replace_revisions": {first["memory_id"]: 2},
        },
    )
    assert (
        "lead with risks" in (await api(client, "/chat", {"question": "Orchid updates"}))["answer"]
    )
    stale = await api(
        client,
        "/chat",
        {"question": "Remember: preference response.style = Orchid updates lead with results"},
    )
    assert stale["capture"]["outcome"] == "superseded"

    await api(client, f"/entries/{replacement}/delete", {"expected_revision": 2})
    assert not (await api(client, "/chat", {"question": "Orchid updates"}))["sources"]
    assert (await api(client, "/entries")) == []
    assert "risks" in str(await api(client, "/history"))  # independently retained transcript
    # A repeat is blocked; an old source excerpt cannot be recaptured merely by changing its key.
    replay = await api(
        client, "/chat", {"question": "记住：偏好 response.style = Orchid updates lead with risks"}
    )
    assert replay["capture"]["outcome"] == "forgotten"
    source = next(
        row["id"]
        for row in await api(client, "/history")
        if row["role"] == "user" and row["content"].startswith("更正")
    )
    assert (
        await api(
            client,
            f"/history/{source}/capture",
            {"key": "different.key", "content": "Orchid updates lead with risks"},
        )
    )["outcome"] == "forgotten"


async def test_suggestions_are_opt_in_never_active_and_compare_exact_quotes(personal):
    client, _ = personal
    assert "capture" not in await api(client, "/chat", {"question": "以后给导师写更新，先说结论。"})
    for question in [
        "以后给导师发什么格式？",
        "以后给导师写更新，这次先讲风险。",
        "For this email only, be concise.",
        "We might decide on Orchid next time.",
        "我喜欢这个回答。",
    ]:
        assert "capture" not in await api(
            client, "/chat", {"question": question, "suggest_memory": True}
        )
    result = await api(
        client, "/chat", {"question": "以后给导师写更新，先说结论。", "suggest_memory": True}
    )
    assert result["capture"]["outcome"] == "created"
    records = await api(client, "/entries")
    [item] = records
    assert item["status"] == "pending"
    assert item["content"] == "以后给导师写更新，先说结论。"
    assert not (await api(client, "/chat", {"question": "导师更新"}))["sources"]


async def test_project_precedence_time_filters_and_request_optout(personal):
    client, config = personal
    db = Store(config.personal_data_dir)
    a = register_project(db, "Orchid")
    b = register_project(db, "Bamboo")
    c = register_project(db, "Secret", "sensitive")
    default = confirm(db, "response.style", "Project update: give a bullet summary.")
    a_only = confirm(db, "response.style", "Project update: send a table.", entity_id=a)
    b_only = confirm(db, "response.style", "Project update: send a sketch.", entity_id=b)
    future = confirm(
        db,
        "project.future",
        "Project update: not yet valid.",
        kind="fact",
        entity_id=a,
        valid_from=datetime.now(UTC) + timedelta(days=1),
    )
    for scope, expected in [(None, default), (a, a_only), (b, b_only)]:
        result = await api(client, "/chat", {"question": "Project update", "project_id": scope})
        assert [entry["path"] for entry in result["sources"]] == [f"memory/{expected}"]
        assert future not in str(result)
    assert not (
        await api(
            client, "/chat", {"question": "Project update", "project_id": a, "use_memory": False}
        )
    )["sources"]
    response = await client.post(
        BASE + "/chat", headers=HEADERS, json={"question": "Project update", "project_id": c}
    )
    assert response.status_code == 403
    confirmed = await api(
        client,
        "/chat",
        {"question": "记住：决策 project.outcome = Project update: retained.", "project_id": a},
    )
    entry = next(
        item
        for item in await api(client, "/entries")
        if item["id"] == confirmed["capture"]["memory_id"]
    )
    assert entry["entity_id"] == a and entry["kind"] == "decision"
    public = await client.post("/api/v1/chat", json={"question": "Project update"})
    assert public.json()["sources"] == []


async def test_historical_capture_is_owner_only_and_verbatim(personal):
    client, _ = personal
    await api(client, "/chat", {"question": "I prefer ✨ illustrated status updates."})
    owner_turn, assistant_turn = await api(client, "/history")
    payload = {
        "kind": "preference",
        "key": "response.style",
        "content": "✨ illustrated status updates",
    }
    path = f"/history/{owner_turn['id']}/capture"
    assert (await client.post(BASE + path, json=payload)).status_code == 401
    assert (
        await client.post(
            BASE + f"/history/{assistant_turn['id']}/capture", json=payload, headers=HEADERS
        )
    ).status_code == 404
    assert (
        await client.post(BASE + path, headers=HEADERS, json={**payload, "content": "fabricated"})
    ).status_code == 422
    assert (await api(client, path, payload))["outcome"] == "created"
    assert (await api(client, path, payload))["outcome"] == "existing"
    record = (await api(client, "/entries"))[0]
    assert record["source"] == f"turn:{owner_turn['id']}" and record["status"] == "pending"


async def test_scoped_provider_context_and_command_non_delivery(
    personal, configured_private_provider, monkeypatch
):
    import app.provider as provider

    client, config = personal
    db = Store(config.personal_data_dir)
    a = register_project(db, "Orchid")
    b = register_project(db, "Bamboo")
    confirm(db, "response.style", "Default style: bullet points.")
    confirm(db, "response.style", "Orchid style: table.", entity_id=a)
    confirm(db, "response.style", "Bamboo style: slide.", entity_id=b)
    confirm(db, "food.preference", "Cauliflower")
    db.save_chat("OldTranscriptMarker", "Old assistant output")
    calls = []

    async def fake_completion(**kwargs):
        calls.append(kwargs["messages"])
        return "Fictional model output"

    monkeypatch.setattr(provider, "request_completion", fake_completion)
    saved = await api(
        client,
        "/chat",
        {"question": "Remember: fact data.reference = PrivateCapture", "allow_provider": True},
    )
    assert saved["capture"]["outcome"] == "created"
    assert calls == []

    await api(
        client,
        "/chat",
        {"question": "Draft one paragraph only", "project_id": a, "allow_provider": True},
    )
    assert [item["role"] for item in calls[0]] == ["system", "user"]
    context = calls[0][0]["content"]
    assert "Orchid style: table." in context and "Bamboo style" not in context
    assert "Default style" not in context and "OldTranscriptMarker" not in context
    assert "PrivateCapture" not in context and "for this reply" in context
    assert "Cauliflower" not in context

    manager = DisclosureManager(db)
    manager.configure(
        DisclosurePolicy(
            enabled=True,
            target_id=target_id(config.llm_base_url, config.llm_model),
            labels=["private", "public"],
            entity_ids=[b],
        ),
        manager.settings()["revision"],
    )
    denied = await client.post(
        BASE + "/chat",
        headers=HEADERS,
        json={"question": "Draft update", "project_id": a, "allow_provider": True},
    )
    assert denied.status_code == 403 and len(calls) == 1


@pytest.mark.parametrize(
    "command",
    [
        "Correct: fix this",
        "更正：偏好 style =   ",
        "Remember:",
        "Remember: preference style = " + "x" * 2001,
    ],
)
def test_invalid_explicit_command_is_not_a_model_question(command):
    result = propose(command, suggest=True, project_id=None)
    assert result.explicit and result.entry is None


@pytest.mark.parametrize(
    ("command", "kind", "key", "value"),
    [
        (
            "Remember:  FACT\t  Identity.Role \t= Optical engineer",
            "fact",
            "identity.role",
            "Optical engineer",
        ),
        (
            "更正：偏好 response.style ＝ 项目＝Orchid 时先写结论",
            "preference",
            "response.style",
            "项目＝Orchid 时先写结论",
        ),
        (
            "记住：决策 project.notes=Keep mode = draft",
            "decision",
            "project.notes",
            "Keep mode = draft",
        ),
    ],
)
def test_typed_capture_preserves_literal_content_and_ascii_field(command, kind, key, value):
    result = propose(command, suggest=False, project_id=None)
    assert result.explicit and result.entry is not None
    assert (result.entry.kind, result.entry.key, result.entry.content) == (kind, key, value)


async def test_closed_fields_use_scoped_confirmed_memory_not_markdown(
    personal, configured_private_provider, monkeypatch
):
    import app.provider as provider

    client, config = personal
    db = Store(config.personal_data_dir)
    (db.root / "knowledge").mkdir()
    (db.root / "knowledge" / "decoy.md").write_text(
        "# Not a current memory\n\nWhat is my role? Museum curator.", encoding="utf-8"
    )
    (Path(config.knowledge_dir) / "example.md").write_text(
        "# Fictional example\n\nWhat is my role? Violin maker.", encoding="utf-8"
    )
    calls = []

    async def fake_completion(**kwargs):
        calls.append(kwargs["messages"])
        return "Synthetic role answer"

    monkeypatch.setattr(provider, "request_completion", fake_completion)
    request = {"question": "What is my role?", "allow_provider": True}
    missing = await api(client, "/chat", request)
    assert missing["recall"] == {"field": "role", "status": "unavailable"}
    assert missing["sources"] == [] and calls == []

    role_id = confirm(db, "identity.role", "Optical systems engineer", kind="fact")
    local = await api(client, "/chat", {"question": "请问：我做什么工作？"})
    assert local["recall"] == {"field": "role", "status": "available"}
    assert local["sources"] == [
        {
            "path": f"memory/{role_id}",
            "excerpt": "identity.role: Optical systems engineer",
            "reason": "field",
            "revision": 2,
        }
    ]
    disabled = await api(client, "/chat", {**request, "use_memory": False})
    assert disabled["recall"]["status"] == "disabled" and calls == []
    await api(client, "/chat", request)
    assert len(calls) == 1 and "Optical systems engineer" in calls[0][0]["content"]
    assert "Museum curator" not in str(calls) and "Violin maker" not in str(calls)

    # A distinct canonical alias can contain a conflicting value; don't pick by age.
    confirm(db, "job.title", "Museum curator", kind="fact")
    conflict = await api(client, "/chat", request)
    assert conflict["recall"]["status"] == "disputed"
    assert conflict["sources"] == [] and len(calls) == 1


def test_new_alias_conflict_prevents_delivery_of_an_old_recall(tmp_path):
    db = Store(str(tmp_path))
    confirm(db, "identity.role", "Optical systems engineer", kind="fact")
    old_matches = db.chat_recall("What is my role?").matches
    target = target_id("https://fixture.invalid/v1", "fictional")
    manager = DisclosureManager(db)
    manager.configure(
        DisclosurePolicy(enabled=True, target_id=target, labels=["public", "private"]), 1
    )
    confirm(db, "job.title", "Museum curator", kind="fact")
    assert (
        manager.authorize(
            target,
            [("memory", match) for match in old_matches],
            chat_scope=True,
            recall_question="What is my role?",
            expected_owner_id=db.owner_id,
        )
        == []
    )


def test_revised_source_is_not_delivered_with_an_old_revision(tmp_path):
    db = Store(str(tmp_path))
    item_id = confirm(db, "identity.role", "Optical systems engineer", kind="fact")
    old_matches = db.chat_recall("What is my role?").matches
    db.edit(item_id, Entry(key="identity.role", content="Optical systems engineer"), 2)
    db.confirm(item_id, [], 3)
    new_matches = db.chat_recall("What is my role?").matches
    same_text = old_matches[0].excerpt == new_matches[0].excerpt
    assert same_text and old_matches[0].revision != new_matches[0].revision
    target = target_id("https://fixture.invalid/v1", "fictional")
    manager = DisclosureManager(db)
    manager.configure(
        DisclosurePolicy(enabled=True, target_id=target, labels=["public", "private"]), 1
    )
    authorize = {"chat_scope": True, "recall_question": "What is my role?"}
    assert manager.authorize(target, [("memory", old_matches[0])], **authorize) == []
    assert manager.authorize(target, [("memory", new_matches[0])], **authorize) == list(new_matches)
