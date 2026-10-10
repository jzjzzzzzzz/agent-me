import pytest

from app.memory import Entry, Store
from app.memory_models import MemoryExport

H = {"Authorization": "Bearer " + "t" * 40}
BASE = "/api/v1/personal"


async def test_identity_api_ownership_review_resolution_relationships_and_history(personal):
    client, _ = personal
    for path in (
        "/identity/entities",
        "/identity/relationships",
        "/retention/policy",
        "/retention/plans",
    ):
        assert (await client.get(BASE + path)).status_code == 401
    person = (
        await client.post(
            BASE + "/identity/entities",
            headers=H,
            json={"kind": "person", "name": "Alex Example", "aliases": ["Alex"]},
        )
    ).json()
    project = (
        await client.post(
            BASE + "/identity/entities", headers=H, json={"kind": "project", "name": "Orchid Demo"}
        )
    ).json()
    assert person["status"] == "pending"
    result = await client.post(BASE + "/identity/resolve", headers=H, json={"name": "Alex"})
    assert result.json()["status"] == "unknown"
    for item in (person, project):
        response = await client.post(
            BASE + f"/identity/entities/{item['id']}/confirm",
            headers=H,
            json={"expected_revision": 1},
        )
        assert response.status_code == 200
    resolved = await client.post(BASE + "/identity/resolve", headers=H, json={"name": "Alex"})
    assert resolved.json()["status"] == "resolved"
    assert resolved.headers["cache-control"] == "no-store"
    record = (
        await client.post(
            BASE + "/entries",
            headers=H,
            json={
                "key": "project.role",
                "content": "Alex works on Orchid",
                "entity_id": person["id"],
                "confidence": 0.8,
            },
        )
    ).json()
    assert record["owner_id"] == person["owner_id"]
    await client.post(
        BASE + f"/entries/{record['id']}/confirm", headers=H, json={"expected_revision": 1}
    )
    edge = (
        await client.post(
            BASE + "/identity/relationships",
            headers=H,
            json={
                "from_entity_id": person["id"],
                "to_entity_id": project["id"],
                "predicate": "works_on",
                "evidence_id": record["id"],
            },
        )
    ).json()
    assert edge["status"] == "pending"
    await client.post(
        BASE + f"/identity/relationships/{edge['id']}/confirm",
        headers=H,
        json={"expected_revision": 1},
    )
    graph = (
        await client.get(BASE + f"/identity/entities/{person['id']}/neighbours", headers=H)
    ).json()
    assert graph["relationships"][0]["id"] == edge["id"]
    history = (
        await client.get(BASE + f"/identity/entities/{person['id']}/history", headers=H)
    ).json()
    assert [row["change"] for row in history] == ["created", "confirmed"]
    exported = MemoryExport.model_validate((await client.get(BASE + "/export", headers=H)).json())
    assert exported.version == 7 and len(exported.relationships) == 1


async def test_entity_api_edits_preserve_sensitive_labels_and_require_review(personal):
    client, _ = personal
    item = (
        await client.post(
            BASE + "/identity/entities",
            headers=H,
            json={
                "kind": "person",
                "name": "Synthetic sensitive",
                "aliases": ["Synthetic"],
                "sensitivity": "sensitive",
            },
        )
    ).json()
    await client.post(
        BASE + f"/identity/entities/{item['id']}/confirm", headers=H, json={"expected_revision": 1}
    )
    response = await client.post(
        BASE + f"/identity/entities/{item['id']}/edit",
        headers=H,
        json={"kind": "person", "name": "Renamed sensitive", "expected_revision": 2},
    )
    assert response.status_code == 200
    assert response.json()["sensitivity"] == "sensitive"
    assert response.json()["aliases"] == ["Synthetic"]
    assert response.json()["status"] == "pending"


async def test_temporal_and_uncertain_memory_is_explicit_not_current_fact(personal):
    client, _ = personal
    record = (
        await client.post(
            BASE + "/entries",
            headers=H,
            json={
                "key": "project",
                "content": "ExpiredOrchid",
                "valid_until": "2020-01-01T00:00:00Z",
                "confidence": 0.6,
            },
        )
    ).json()
    await client.post(BASE + f"/entries/{record['id']}/confirm", headers=H, json={})
    assert (await client.post(BASE + "/memory/select", headers=H, json={})).json() == []
    selected = (
        await client.post(BASE + "/memory/select", headers=H, json={"include_uncertain": True})
    ).json()
    assert selected[0]["effective_belief"] == "outdated"
    past = (
        await client.post(
            BASE + "/memory/select", headers=H, json={"as_of": "2019-01-01T00:00:00Z"}
        )
    ).json()
    assert past[0]["effective_belief"] == "known"
    invalid = await client.post(BASE + "/memory/select", headers=H, json={"as_of": "2019-01-01"})
    assert invalid.status_code == 422


async def test_retention_api_requires_preview_and_stale_safe_policy(personal):
    client, config = personal
    db = Store(config.personal_data_dir)
    item = db.add(Entry(key="project", content="SyntheticOrchid"))
    with db.connect() as connection:
        connection.execute(
            "UPDATE entries SET updated_at='2020-01-01T00:00:00Z' WHERE id=?", (item["id"],)
        )
    response = await client.post(
        BASE + "/retention/policy",
        headers=H,
        json={"policy": {"pending_days": 1}, "expected_revision": 1},
    )
    assert response.status_code == 200 and response.json()["revision"] == 2
    plan = (await client.post(BASE + "/retention/preview", headers=H, json={})).json()
    assert plan["targets"][0]["id"] == item["id"] and db.entries()
    result = await client.post(BASE + f"/retention/plans/{plan['id']}/apply", headers=H, json={})
    assert result.status_code == 200 and result.json()["status"] == "applied"
    assert not db.entries()
    assert result.headers["cache-control"] == "no-store"
    assert (
        await client.post(
            BASE + "/retention/preview", headers=H, json={"entity_id": "misleading-filter"}
        )
    ).status_code == 422


@pytest.mark.parametrize(
    "extra",
    [{"owner_id": "forged"}, {"status": "confirmed"}, {"revision": 10}, {"distinct": "false"}],
)
async def test_entity_contract_rejects_client_control_of_metadata(personal, extra):
    client, _ = personal
    response = await client.post(
        BASE + "/identity/entities",
        headers=H,
        json={"kind": "person", "name": "Synthetic", **extra},
    )
    assert response.status_code == 422
