import json

import httpx
import pytest

from app.audit import AuditLog
from app.disclosure import DisclosureManager, target_id
from app.identity import IdentityStore
from app.knowledge import Document, Match
from app.memory import Entry, MemoryConflict, MemoryPermissionDenied, Store
from app.memory_models import EntityInput
from app.owner_models import DisclosurePolicy
from app.portability import PortableMemory
from app.provider import generate_answer

H = {"Authorization": "Bearer " + "t" * 40}
BASE = "/api/v1/personal"


def match(path, value):
    return Match(Document("Fictional", path, value), value, 1)


def test_disclosure_defaults_target_labels_scopes_and_stale_data(tmp_path):
    db = Store(str(tmp_path / "source"))
    person = IdentityStore(db).add(EntityInput(kind="person", name="Fictional Alex"))
    IdentityStore(db).confirm(person["id"], 1)
    item = db.add(Entry(key="project", content="FictionalOrchid", entity_id=person["id"]))
    db.confirm(item["id"], [], 1)
    manager = DisclosureManager(db)
    target = target_id("https://fixture.invalid/v1", "fictional")
    inputs = [
        ("memory", db.context("FictionalOrchid")[0]),
        ("private", match("private/knowledge/note.md", "PrivateDocument")),
        ("public", match("example.md", "PublicDocument")),
    ]
    with pytest.raises(MemoryPermissionDenied):
        manager.authorize(target, inputs)
    manager.configure(DisclosurePolicy(enabled=True, target_id=target), 1)
    assert [item.excerpt for item in manager.authorize(target, inputs)] == [
        "project: FictionalOrchid",
        "PublicDocument",
    ]
    with pytest.raises(MemoryPermissionDenied):
        manager.authorize(target_id("https://other.invalid", "fictional"), inputs)
    with pytest.raises(MemoryConflict):
        manager.configure(DisclosurePolicy(), 1)
    manager.configure(
        DisclosurePolicy(
            enabled=True,
            target_id=target,
            namespaces=["private"],
            document_paths=["private/other.md"],
        ),
        2,
    )
    assert manager.authorize(target, inputs) == []
    manager.configure(DisclosurePolicy(enabled=True, target_id=target, entity_ids=[]), 3)
    assert [item.excerpt for item in manager.authorize(target, inputs)] == ["PublicDocument"]
    manager.configure(DisclosurePolicy(enabled=True, target_id=target, memory_ids=[]), 4)
    assert [item.excerpt for item in manager.authorize(target, inputs)] == ["PublicDocument"]
    manager.configure(DisclosurePolicy(enabled=True, target_id=target), 5)
    db.edit(item["id"], Entry(key="project", content="CorrectedCedar"), 2)
    assert [item.excerpt for item in manager.authorize(target, inputs)] == ["PublicDocument"]
    # A provider grant is inspection history after a move, never restored authority.
    destination = Store(str(tmp_path / "destination"))
    portable = PortableMemory(destination)
    data = db.export()
    portable.apply(data, portable.preview(data)["digest"])
    assert not DisclosureManager(destination).settings()["policy"]["enabled"]
    assert destination.export()["import_archives"][0]["authority"]["disclosure_permissions"][0][
        "policy"
    ]["enabled"]
    assert "PrivateDocument" not in json.dumps(AuditLog(db).events())


def test_live_subject_privacy_cannot_bypass_request_sensitive_opt_in(tmp_path, monkeypatch):
    db = Store(str(tmp_path))
    identity = IdentityStore(db)
    person = identity.add(EntityInput(kind="person", name="Fictional Alex"))
    identity.confirm(person["id"], 1)
    item = db.add(Entry(key="project", content="FictionalOrchid", entity_id=person["id"]))
    db.confirm(item["id"], [], 1)
    inputs = [("memory", db.context("FictionalOrchid")[0])]
    target = target_id("https://fixture.invalid", "fictional")
    manager = DisclosureManager(db)
    manager.configure(
        DisclosurePolicy(enabled=True, target_id=target, labels=["public", "private", "sensitive"]),
        1,
    )
    original = db.select

    def raise_privacy_after_selection(query):
        rows = original(query)
        identity.edit(
            person["id"],
            EntityInput(kind="person", name="Fictional Alex", sensitivity="sensitive"),
            2,
        )
        identity.confirm(person["id"], 3)
        return rows

    monkeypatch.setattr(db, "select", raise_privacy_after_selection)
    assert manager.authorize(target, inputs, allow_sensitive=False) == []
    monkeypatch.setattr(db, "select", original)
    assert len(manager.authorize(target, inputs, allow_sensitive=True)) == 1


async def test_configured_provider_stays_local_without_both_owner_opt_ins(personal, monkeypatch):
    from app import personal as module

    client, config = personal
    config.llm_base_url, config.llm_api_key, config.llm_model = (
        "https://fixture.invalid",
        "fixture",
        "model",
    )
    calls = []

    async def forbidden(**kwargs):
        calls.append(kwargs)
        raise AssertionError("No provider dispatch authorized")

    monkeypatch.setattr(module, "generate_answer", forbidden)
    assert (
        await client.post(BASE + "/chat", headers=H, json={"question": "Fictional query"})
    ).json()["mode"] == "extractive"
    assert (
        await client.post(
            BASE + "/chat", headers=H, json={"question": "Fictional query", "allow_provider": True}
        )
    ).status_code == 403
    assert not calls
    target = (await client.get(BASE + "/disclosure/target", headers=H)).json()["target_id"]
    result = await client.post(
        BASE + "/disclosure/policy",
        headers=H,
        json={"expected_revision": 1, "policy": {"enabled": True, "target_id": target}},
    )
    assert result.status_code == 200
    assert (
        await client.post(BASE + "/chat", headers=H, json={"question": "Fictional query"})
    ).json()["mode"] == "extractive"
    assert not calls
    assert (
        await client.post(
            BASE + "/disclosure/policy",
            headers=H,
            json={"expected_revision": 2, "policy": {"enabled": True, "target_id": "0" * 64}},
        )
    ).status_code == 403


async def test_actual_outbound_payload_honors_sensitive_documents_target_and_record_scope(
    personal, monkeypatch, configured_private_provider
):
    from app import personal as module

    client, config = personal
    db = Store(config.personal_data_dir)
    secret = db.add(
        Entry(kind="preference", key="style", content="SensitiveOrchid", sensitivity="sensitive")
    )
    db.confirm(secret["id"], [], 1)
    doc_dir = db.root / "knowledge"
    doc_dir.mkdir()
    (doc_dir / "note.md").write_text("# Fictional\n\nPrivateOrchid document.", encoding="utf-8")
    payloads = []

    def handle(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "Fictional answer"}}]})

    async def via_mock(**kwargs):
        return await generate_answer(**kwargs, transport=httpx.MockTransport(handle))

    monkeypatch.setattr(module, "generate_answer", via_mock)
    request = {"question": "PrivateOrchid", "allow_provider": True}
    assert (await client.post(BASE + "/chat", headers=H, json=request)).status_code == 200
    assert "SensitiveOrchid" not in json.dumps(payloads[-1]) and "document." not in json.dumps(
        payloads[-1]
    )
    assert (
        await client.post(BASE + "/chat", headers=H, json={**request, "allow_sensitive": True})
    ).status_code == 200
    assert "SensitiveOrchid" in json.dumps(payloads[-1]) and "document." not in json.dumps(
        payloads[-1]
    )
    target = target_id(config.llm_base_url, config.llm_model)
    manager = DisclosureManager(db)
    manager.configure(
        DisclosurePolicy(
            enabled=True,
            target_id=target,
            namespaces=["private"],
            document_paths=["private/note.md"],
        ),
        2,
    )
    await client.post(BASE + "/chat", headers=H, json=request)
    assert "PrivateOrchid document." in json.dumps(
        payloads[-1]
    ) and "SensitiveOrchid" not in json.dumps(payloads[-1])
    config.llm_model = "changed-target"
    response = await client.post(BASE + "/chat", headers=H, json=request)
    assert response.status_code == 403 and len(payloads) == 3
