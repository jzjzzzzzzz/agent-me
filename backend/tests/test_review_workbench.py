"""Browser review sequence against actual authenticated API/core contracts."""

import pytest

from app.learning_policy import LearningPolicyManager
from app.memory import MemoryConflict, MemoryNotFound, Store
from app.memory_models import Entry, LearningPolicy

BASE = "/api/v1/personal"
HEADERS = {"Authorization": "Bearer " + "t" * 40}


async def test_review_workbench_source_candidate_evidence_correction_and_erasure(personal):
    client, config = personal
    db = Store(config.personal_data_dir)
    LearningPolicyManager(db).configure(
        LearningPolicy(require_revision_key_prefixes=["identity."]), 1
    )

    async def post(path, body):
        response = await client.post(BASE + path, json=body, headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        return response.json()

    async def get(path):
        response = await client.get(BASE + path, headers=HEADERS)
        assert response.status_code == 200
        return response.json()

    source = await post(
        "/learning/sources",
        {"kind": "document", "name": "Fictional profile", "sensitivity": "private"},
    )
    assert not source["approved"]
    source = await post(
        f"/learning/sources/{source['id']}/review",
        {"approved": True, "expected_revision": source["revision"]},
    )
    run = await post(
        f"/learning/sources/{source['id']}/ingest",
        {
            "content": "fact identity.name: Alex Example",
            "mode": "fields",
            "expected_source_revision": source["revision"],
        },
    )
    assert run["status"] == "completed"
    memory = (await get("/entries?include_superseded=true"))[0]
    assert memory["status"] == "pending"
    assert (await post("/ask", {"question": "What is my name?"}))["status"] == "unknown"
    origins = await get(f"/entries/{memory['id']}/origins")
    assert origins[0]["excerpt"] == "Alex Example"
    assert origins[0]["source_id"] == source["id"]
    await post(
        f"/entries/{memory['id']}/confirm",
        {"expected_revision": memory["revision"], "replace_ids": [], "replace_revisions": {}},
    )
    memory = (await get("/entries"))[0]
    answer = await post("/ask", {"question": "What is my name?", "allow_sensitive": False})
    assert answer["status"] == "known"
    assert answer["evidence"][0]["path"] == f"memory/{memory['id']}@{memory['revision']}"
    assert answer["evidence"][0]["value"] == "Alex Example"
    assert not await get("/history")

    await post(
        f"/entries/{memory['id']}/edit",
        {
            "kind": memory["kind"],
            "key": memory["key"],
            "content": "River Example",
            "expected_revision": memory["revision"],
        },
    )
    assert (await post("/ask", {"question": "What is my name?"}))["status"] == "unknown"
    stale_delete = await client.post(
        BASE + f"/entries/{memory['id']}/delete",
        headers=HEADERS,
        json={"expected_revision": memory["revision"]},
    )
    assert stale_delete.status_code == 409
    edited = (await get("/entries"))[0]
    history = await get(f"/entries/{memory['id']}/history")
    assert [item["change"] for item in history] == ["created", "confirmed", "edited"]
    assert history[0]["content"] == "Alex Example"
    assert edited["content"] == "River Example"
    await post(f"/entries/{edited['id']}/delete", {"expected_revision": edited["revision"]})
    assert not await get("/entries?include_superseded=true")
    assert (await post("/ask", {"question": "What is my name?"}))["status"] == "unknown"
    for suffix in ("history", "origins"):
        assert (
            await client.get(BASE + f"/entries/{edited['id']}/{suffix}", headers=HEADERS)
        ).status_code == 404
    source = await post(
        f"/learning/sources/{source['id']}/review",
        {"approved": False, "expected_revision": source["revision"]},
    )
    assert not source["approved"]
    assert (
        await client.post(
            BASE + f"/learning/sources/{source['id']}/ingest",
            headers=HEADERS,
            json={
                "content": "fact identity.name: Alex Example",
                "expected_source_revision": source["revision"],
            },
        )
    ).status_code == 403


def test_revision_bound_delete_protects_changed_and_missing_memory(tmp_path):
    db = Store(tmp_path)
    entry = db.add(Entry(key="profile.name", content="Alex Example"))
    db.confirm(entry["id"], [])
    with pytest.raises(MemoryConflict):
        db.delete(entry["id"], entry["revision"])
    assert db.entries()[0]["status"] == "confirmed"
    db.delete(entry["id"], entry["revision"] + 1)
    with pytest.raises(MemoryNotFound):
        db.delete(entry["id"], entry["revision"] + 1)
    # Legacy unconditioned deletes retain their idempotent behavior.
    assert db.delete(entry["id"]) == {"deleted": True}


@pytest.mark.parametrize("revision", [True, 0, "1", 1.5])
async def test_delete_precondition_is_strict(personal, revision):
    client, _ = personal
    response = await client.post(
        BASE + "/entries/missing/delete",
        headers=HEADERS,
        json={"expected_revision": revision},
    )
    assert response.status_code == 422


async def test_delete_without_body_remains_compatible(personal):
    client, _ = personal
    response = await client.post(BASE + "/entries/missing/delete", headers=HEADERS)
    assert response.status_code == 200 and response.json() == {"deleted": True}
