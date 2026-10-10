"""Owner-visible identity review, live preconditions and exact cascade-deletion scopes."""

import pytest

from app.identity import IdentityStore
from app.learning import LearningPipeline
from app.memory import MemoryConflict, MemoryInputError, Store
from app.memory_models import EntityInput, Entry, IngestionInput, RelationshipInput, SourceInput

BASE = "/api/v1/personal"
H = {"Authorization": "Bearer " + "t" * 40}


def entity(identity, name, kind="person"):
    row = identity.add(EntityInput(kind=kind, name=name, aliases=[name.split()[0]]))
    return identity.confirm(row["id"], row["revision"])


def fixture_graph(root):
    db = Store(root)
    identity = IdentityStore(db)
    person = entity(identity, "Alex Example")
    project = entity(identity, "Orchid Demo", "project")
    other = entity(identity, "River Example")
    identity.bind_owner(person["id"])
    learning = LearningPipeline(db)
    source = learning.register(
        SourceInput(kind="document", name="Fictional role", entity_id=person["id"])
    )
    source = learning.approve(source["id"], expected_revision=source["revision"])
    run = learning.ingest(
        source["id"], IngestionInput(content="fact project.role: Works on Orchid")
    )
    memory_id = run["items"][0]["memory_id"]
    db.confirm(memory_id, [])
    memory = db.entries()[0]
    edge = identity.relate(
        RelationshipInput(
            from_entity_id=other["id"],
            to_entity_id=project["id"],
            predicate="works_on",
            evidence_id=memory_id,
        )
    )
    edge = identity.confirm(edge["id"], edge["revision"], relationship=True)
    return db, identity, learning, person, project, other, source, memory, edge


def test_delete_preview_covers_historical_links_and_indirect_evidence_edges(tmp_path):
    db, identity, _, person, project, other, source, memory, edge = fixture_graph(tmp_path)
    db.edit(
        memory["id"],
        Entry(key=memory["key"], content="Updated role", entity_id=other["id"]),
        memory["revision"],
    )
    independent = db.add(Entry(key="notes.independent", content="Independent fictional memory"))
    db.save_chat("Synthetic transcript", "Independent transcript")
    preview = identity.preview_delete(person["id"])
    assert preview == identity.preview_delete(person["id"])
    assert preview["owner_binding"]
    assert [row["id"] for row in preview["memories"]] == [memory["id"]]
    assert preview["memories"][0]["entity_id"] == other["id"]
    assert [row["id"] for row in preview["relationships"]] == [edge["id"]]
    assert [row["id"] for row in preview["sources"]] == [source["id"]]
    assert len(preview["runs"]) == preview["origin_count"] == 1
    assert preview["history_count"] == 7  # entity 2 + memory 3 + relationship 2
    assert len(db.entries()) == 2 and identity.owner()["entity_id"] == person["id"]
    identity.delete(person["id"], expected_revision=person["revision"], digest=preview["digest"])
    assert [row["id"] for row in db.entries()] == [independent["id"]]
    assert not identity.relationships() and not identity.owner()["entity_id"]
    assert {row["id"] for row in identity.entities()} == {project["id"], other["id"]}
    exported = db.export()
    assert not exported["sources"] and not exported["origins"] and not exported["ingestion_runs"]
    assert len(db.history()) == 2


@pytest.mark.parametrize("change", ["memory", "source", "new_memory", "owner", "endpoint"])
def test_entity_deletion_rejects_changed_scope_without_partial_effects(tmp_path, change):
    db, identity, learning, person, _, other, source, memory, _ = fixture_graph(tmp_path)
    preview = identity.preview_delete(person["id"])
    if change == "memory":
        db.edit(
            memory["id"], Entry(key=memory["key"], content="Changed evidence"), memory["revision"]
        )
    elif change == "source":
        learning.approve(source["id"], approved=False, expected_revision=source["revision"])
    elif change == "new_memory":
        db.add(Entry(key="new.fact", content="New dependent memory", entity_id=person["id"]))
    elif change == "owner":
        identity.bind_owner(other["id"])
    else:
        identity.edit(
            person["id"], EntityInput(kind="person", name="Updated person"), person["revision"]
        )
    before = db.export()
    with pytest.raises(MemoryConflict):
        identity.delete(
            person["id"], expected_revision=person["revision"], digest=preview["digest"]
        )
    assert db.export() == before


def test_relationship_delete_preview_preserves_evidence_and_entities(tmp_path):
    db, identity, _, person, _, _, _, memory, edge = fixture_graph(tmp_path)
    preview = identity.preview_delete(edge["id"], relationship=True)
    assert preview["kind"] == "relationship"
    assert (
        preview["memories"]
        == preview["sources"]
        == preview["runs"]
        == preview["relationships"]
        == []
    )
    assert preview["history_count"] == 2 and preview["origin_count"] == 0
    assert not preview["owner_binding"]
    identity.delete(
        edge["id"], relationship=True, expected_revision=edge["revision"], digest=preview["digest"]
    )
    assert db.entries()[0]["id"] == memory["id"] and len(identity.entities()) == 3
    assert identity.owner()["entity_id"] == person["id"]


def test_owner_binding_reviews_current_binding_and_target_revision(tmp_path):
    identity = IdentityStore(Store(tmp_path))
    person = entity(identity, "Alex Example")
    other = entity(identity, "River Example")
    identity.bind_owner(
        person["id"], expected_owner_entity_id=None, expected_entity_revision=person["revision"]
    )
    with pytest.raises(MemoryConflict):
        identity.bind_owner(
            other["id"], expected_owner_entity_id=None, expected_entity_revision=other["revision"]
        )
    edited = identity.edit(
        other["id"], EntityInput(kind="person", name="Renamed person"), other["revision"]
    )
    identity.confirm(edited["id"], edited["revision"])
    with pytest.raises(MemoryConflict):
        identity.bind_owner(
            other["id"],
            expected_owner_entity_id=person["id"],
            expected_entity_revision=other["revision"],
        )
    with pytest.raises(MemoryInputError):
        identity.edit(
            person["id"],
            EntityInput(kind="project", name="Invalid owner project"),
            person["revision"],
        )
    assert identity.owner()["entity_id"] == person["id"]
    identity.bind_owner(None, expected_owner_entity_id=person["id"])
    assert identity.owner()["entity_id"] is None
    assert (
        identity.edit(
            person["id"], EntityInput(kind="project", name="Unbound project"), person["revision"]
        )["kind"]
        == "project"
    )


def test_relationship_proposals_and_confirmation_bind_endpoint_and_evidence_revisions(tmp_path):
    db = Store(tmp_path)
    identity = IdentityStore(db)
    a, b = entity(identity, "Alex Example"), entity(identity, "Orchid Demo", "project")
    memory = db.add(Entry(key="project.role", content="Synthetic role"))
    db.confirm(memory["id"], [])
    payload = RelationshipInput(
        from_entity_id=a["id"], to_entity_id=b["id"], predicate="works_on", evidence_id=memory["id"]
    )
    revisions = {a["id"]: a["revision"], b["id"]: b["revision"]}
    with pytest.raises(MemoryConflict):
        identity.relate(payload, expected_evidence_revision=1, expected_entity_revisions=revisions)
    with pytest.raises(MemoryInputError):
        identity.relate(
            payload, expected_evidence_revision=2, expected_entity_revisions={a["id"]: 2}
        )
    edge = identity.relate(
        payload, expected_evidence_revision=2, expected_entity_revisions=revisions
    )
    edited = identity.edit(
        b["id"], EntityInput(kind="project", name="Updated Orchid"), b["revision"]
    )
    identity.confirm(edited["id"], edited["revision"])
    with pytest.raises(MemoryConflict):
        identity.confirm(
            edge["id"], edge["revision"], relationship=True, expected_entity_revisions=revisions
        )
    revisions[b["id"]] = edited["revision"] + 1
    assert (
        identity.confirm(
            edge["id"], edge["revision"], relationship=True, expected_entity_revisions=revisions
        )["status"]
        == "confirmed"
    )


async def test_identity_review_api_auth_previews_and_reviewed_deletion(personal):
    client, config = personal
    _, identity, _, person, _, _, _, _, edge = fixture_graph(config.personal_data_dir)
    for path in [
        f"/identity/entities/{person['id']}/delete-preview",
        f"/identity/relationships/{edge['id']}/delete-preview",
    ]:
        assert (await client.get(BASE + path)).status_code == 401
    path = BASE + f"/identity/entities/{person['id']}"
    response = await client.get(path + "/delete-preview", headers=H)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    preview = response.json()
    assert preview["record"]["id"] == person["id"] and len(preview["memories"]) == 1
    bad = await client.post(
        path + "/delete",
        headers=H,
        json={"expected_revision": person["revision"], "digest": "0" * 64},
    )
    assert bad.status_code == 409 and len(identity.entities()) == 3
    result = await client.post(
        path + "/delete",
        headers=H,
        json={"expected_revision": person["revision"], "digest": preview["digest"]},
    )
    assert result.status_code == 200 and result.json() == {"deleted": True}
    assert (await client.get(path + "/delete-preview", headers=H)).status_code == 404
    assert (await client.post(path + "/delete", headers=H)).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"expected_revision": True},
        {"expected_revision": 0},
        {"digest": "x"},
        {"digest": "a" * 64},
        {"expected_revision": 1, "digest": "a" * 64, "approved": True},
    ],
)
async def test_identity_delete_strict_review_payload(personal, payload):
    client, _ = personal
    response = await client.post(
        BASE + "/identity/entities/missing/delete", headers=H, json=payload
    )
    assert response.status_code == 422


async def test_owner_and_relationship_live_review_api(personal):
    client, config = personal
    _, identity, _, person, project, _, _, memory, _ = fixture_graph(config.personal_data_dir)
    binding = await client.post(
        BASE + "/identity/owner",
        headers=H,
        json={
            "entity_id": person["id"],
            "expected_owner_entity_id": None,
            "expected_entity_revision": person["revision"],
        },
    )
    assert binding.status_code == 409
    response = await client.post(
        BASE + "/identity/relationships",
        headers=H,
        json={
            "from_entity_id": person["id"],
            "to_entity_id": project["id"],
            "predicate": "works_on",
            "evidence_id": memory["id"],
            "expected_evidence_revision": memory["revision"],
            "expected_entity_revisions": {person["id"]: person["revision"], project["id"]: 1},
        },
    )
    assert response.status_code == 409 and len(identity.relationships()) == 1
    assert (
        await client.post(
            BASE + "/identity/owner",
            headers=H,
            json={"entity_id": None, "expected_owner_entity_id": person["id"]},
        )
    ).status_code == 200


def test_reviewed_delete_is_atomic_against_a_concurrent_new_dependency(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    db = Store(tmp_path)
    identity = IdentityStore(db)
    person = entity(identity, "Alex Example")
    preview = identity.preview_delete(person["id"])
    barrier = Barrier(2)

    def delete():
        barrier.wait()
        try:
            IdentityStore(Store(tmp_path)).delete(
                person["id"], expected_revision=person["revision"], digest=preview["digest"]
            )
            return "deleted"
        except MemoryConflict:
            return "stale"

    def add():
        barrier.wait()
        try:
            Store(tmp_path).add(
                Entry(
                    key="concurrent.fact",
                    content="Unreviewed new dependency",
                    entity_id=person["id"],
                )
            )
            return "added"
        except MemoryConflict:
            return "missing"

    with ThreadPoolExecutor(max_workers=2) as pool:
        deleted, added = pool.submit(delete), pool.submit(add)
        outcome = (deleted.result(), added.result())
    assert outcome in {("deleted", "missing"), ("stale", "added")}
    if outcome[0] == "stale":
        assert len(db.entries()) == len(identity.entities()) == 1
    else:
        assert not db.entries() and not identity.entities()
