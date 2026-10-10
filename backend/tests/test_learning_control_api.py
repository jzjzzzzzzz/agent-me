from app.memory_models import MemoryExport

H = {"Authorization": "Bearer " + "t" * 40}
BASE = "/api/v1/personal"


async def test_learning_control_api_is_private_reviewed_and_exported(personal):
    client, _ = personal
    assert (await client.get(BASE + "/learning/policy")).status_code == 401
    policy = {"require_revision_key_prefixes": ["profile."]}
    response = await client.post(
        BASE + "/learning/policy", headers=H, json={"policy": policy, "expected_revision": 1}
    )
    assert response.status_code == 200 and response.json()["revision"] == 2
    assert response.headers["cache-control"] == "no-store"
    for _ in range(2):
        assert (
            await client.post(
                BASE + "/entries",
                headers=H,
                json={"key": "profile.name", "content": "Fictional Example"},
            )
        ).status_code == 200
    plan = (await client.post(BASE + "/consolidation/preview", headers=H)).json()
    assert len(plan["groups"]) == 1
    keeper = plan["groups"][0]["keeper_id"]
    assert (
        await client.post(BASE + f"/entries/{keeper}/confirm", headers=H, json={})
    ).status_code == 403
    path = BASE + f"/consolidation/{plan['id']}/apply"
    assert (await client.post(path, headers=H, json={"digest": "0" * 64})).status_code == 409
    result = await client.post(path, headers=H, json={"digest": plan["digest"]})
    assert result.status_code == 200 and result.json()["merged_count"] == 1
    assert result.headers["cache-control"] == "no-store"
    exported = MemoryExport.model_validate((await client.get(BASE + "/export", headers=H)).json())
    assert exported.consolidation_plans[0].status == "applied"
    assert exported.learning_policy.revision == 2
