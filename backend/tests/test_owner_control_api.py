import json

from app.audit import AuditLog
from app.memory import Entry, Store
from app.memory_models import MemoryExport
from app.owner_control import OwnerControl
from app.owner_models import WorkspacePurge

H = {"Authorization": "Bearer " + "t" * 40}
BASE = "/api/v1/personal"


async def test_private_import_preview_digest_apply_and_inert_archives(personal, tmp_path):
    client, config = personal
    source = Store(str(tmp_path / "source"))
    item = source.add(Entry(key="project", content="FictionalOrchid"))
    source.confirm(item["id"], [], 1)
    payload = {"snapshot": source.export()}
    assert (await client.post(BASE + "/portability/preview", json=payload)).status_code == 401
    preview = await client.post(BASE + "/portability/preview", headers=H, json=payload)
    assert preview.status_code == 200 and preview.headers["cache-control"] == "no-store"
    apply = {**payload, "digest": preview.json()["digest"]}
    assert (
        await client.post(
            BASE + "/portability/import", headers=H, json={**apply, "digest": "0" * 64}
        )
    ).status_code == 409
    response = await client.post(BASE + "/portability/import", headers=H, json=apply)
    assert response.status_code == 200 and response.json()["imported"]
    assert Store(config.personal_data_dir).owner_id == source.owner_id
    assert (
        await client.post(BASE + "/portability/import", headers=H, json=apply)
    ).status_code == 409
    archives = (await client.get(BASE + "/portability/archives", headers=H)).json()
    assert len(archives) == 1
    exported = MemoryExport.model_validate((await client.get(BASE + "/export", headers=H)).json())
    assert exported.entries[0].content == "FictionalOrchid" and exported.version == 8


async def test_access_audit_redacts_inputs_and_denied_request_details(personal):
    client, config = personal
    await client.post(
        BASE + "/entries", headers=H, json={"key": "project", "content": "UniquePrivateBodyOrchid"}
    )
    await client.post(BASE + "/ask", headers=H, json={"question": "UniquePrivateQuestionOrchid"})
    denied = await client.post(
        BASE + "/actions",
        headers=H,
        json={
            "tool": "tasks.create",
            "arguments": {"title": "UniquePrivateTaskOrchid"},
            "idempotency_key": "UniquePrivateKey",
        },
    )
    assert denied.status_code == 403
    events = (await client.get(BASE + "/audit", headers=H)).json()
    assert any(item["operation"] == "api.add" for item in events)
    assert any(
        item["operation"] == "api.create_action" and item["outcome"] == "denied" for item in events
    )
    assert "UniquePrivate" not in json.dumps(events) and "Bearer" not in json.dumps(events)
    assert (await client.get(BASE + "/audit")).status_code == 401
    assert (await client.get(BASE + "/audit?limit=1001", headers=H)).status_code == 422
    before = len(AuditLog(Store(config.personal_data_dir)).events(1000))
    await client.post(BASE + "/audit/clear", headers=H)
    after = AuditLog(Store(config.personal_data_dir)).events()
    assert len(after) == 2 < before and {item["operation"] for item in after} == {
        "audit.clear",
        "api.clear_audit",
    }


async def test_private_output_erasure_and_literal_workspace_purge_review(personal):
    client, config = personal
    await client.post(
        BASE + "/tools/permissions/notes.create",
        headers=H,
        json={"enabled": True, "expected_revision": 1},
    )
    plan = (
        await client.post(
            BASE + "/actions",
            headers=H,
            json={
                "tool": "notes.create",
                "arguments": {"title": "Fictional", "content": "IndependentFictionalCopy"},
                "idempotency_key": "note",
            },
        )
    ).json()
    await client.post(
        BASE + f"/actions/{plan['id']}/approve",
        headers=H,
        json={"expected_revision": 1, "digest": plan["digest"]},
    )
    result = (await client.post(BASE + f"/actions/{plan['id']}/execute", headers=H)).json()
    note_id = result["result"]["id"]
    assert (
        await client.post(
            BASE + f"/notes/{note_id}/delete", headers=H, json={"expected_revision": 9}
        )
    ).status_code == 409
    assert (
        await client.post(
            BASE + f"/notes/{note_id}/delete", headers=H, json={"expected_revision": 1}
        )
    ).status_code == 200
    assert (await client.get(BASE + "/actions", headers=H)).json() == []
    db = Store(config.personal_data_dir)
    review = {"expected_owner_id": db.owner_id, "confirmation": "erase-personal-workspace"}
    assert (
        await client.post(
            BASE + "/workspace/purge", headers=H, json={**review, "confirmation": "yes"}
        )
    ).status_code == 422
    assert (
        await client.post(
            BASE + "/workspace/purge",
            headers=H,
            json={**review, "expected_owner_id": "not-this-owner"},
        )
    ).status_code == 409
    response = await client.post(BASE + "/workspace/purge", headers=H, json=review)
    assert (
        response.status_code == 200 and response.json()["owner_id"] != review["expected_owner_id"]
    )
    assert "IndependentFictionalCopy" not in json.dumps(db.export())


async def test_in_flight_chat_cannot_repopulate_a_purged_workspace(
    personal, monkeypatch, configured_private_provider
):
    from app import personal as module

    client, config = personal
    db = Store(config.personal_data_dir)

    async def purge_during_generation(**kwargs):
        OwnerControl(db).purge(
            WorkspacePurge(expected_owner_id=db.owner_id, confirmation="erase-personal-workspace")
        )
        return "StalePrivateAnswer", "extractive"

    monkeypatch.setattr(module, "generate_answer", purge_during_generation)
    response = await client.post(
        BASE + "/chat",
        headers=H,
        json={"question": "Remember: StalePrivatePreference", "allow_provider": True},
    )
    assert response.status_code == 409 and "StalePrivate" not in response.text
    assert not db.history() and not db.entries()
