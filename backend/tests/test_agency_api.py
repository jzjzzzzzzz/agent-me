from app.memory_models import MemoryExport

H = {"Authorization": "Bearer " + "t" * 40}
BASE = "/api/v1/personal"


async def test_tool_api_owner_permissions_plan_approval_execution_and_rollback(personal):
    client, _ = personal
    for path in ("/tools/permissions", "/actions", "/tasks", "/notes"):
        assert (await client.get(BASE + path)).status_code == 401
    invocation = {
        "tool": "tasks.create",
        "arguments": {"title": "Synthetic demo"},
        "idempotency_key": "api-demo",
    }
    assert (await client.post(BASE + "/actions", headers=H, json=invocation)).status_code == 403
    permissions = (await client.get(BASE + "/tools/permissions", headers=H)).json()
    assert all(permission["enabled"] is False for permission in permissions)
    granted = await client.post(
        BASE + "/tools/permissions/tasks.create",
        headers=H,
        json={"enabled": True, "expected_revision": 1},
    )
    assert granted.status_code == 200 and granted.json()["revision"] == 2
    plan = (await client.post(BASE + "/actions", headers=H, json=invocation)).json()
    path = BASE + f"/actions/{plan['id']}"
    assert (await client.post(path + "/execute", headers=H, json={})).status_code == 403
    assert (await client.get(BASE + "/tasks", headers=H)).json() == []
    approval = {"expected_revision": 1, "digest": plan["digest"]}
    assert (await client.post(path + "/approve", headers=H, json=approval)).status_code == 200
    result = await client.post(path + "/execute", headers=H, json={})
    assert result.status_code == 200 and result.json()["status"] == "completed"
    assert result.headers["cache-control"] == "no-store"
    assert len((await client.get(BASE + "/tasks", headers=H)).json()) == 1
    assert (await client.post(BASE + "/actions", headers=H, json=invocation)).json()["id"] == plan[
        "id"
    ]
    assert (await client.post(path + "/execute", headers=H, json={})).json()[
        "result"
    ] == result.json()["result"]
    assert (await client.post(path + "/rollback", headers=H, json={})).json()[
        "status"
    ] == "rolled_back"
    assert (await client.get(BASE + "/tasks", headers=H)).json() == []
    events = (await client.get(path + "/events", headers=H)).json()
    assert events[-1]["stage"] == "rollback"
    exported = MemoryExport.model_validate((await client.get(BASE + "/export", headers=H)).json())
    assert exported.version == 6 and len(exported.action_plans) == 1


async def test_router_knowledge_recommendation_and_act_are_distinct(personal):
    client, _ = personal
    invocation = {
        "tool": "notes.create",
        "arguments": {"title": "Synthetic", "content": "Private fictional note"},
        "idempotency_key": "recommend",
    }
    response = await client.post(
        BASE + "/agent", headers=H, json={"intent": {"kind": "recommend", "invocation": invocation}}
    )
    assert response.status_code == 200
    assert response.json()["kind"] == "recommendation"
    plan = response.json()["result"]
    assert plan["status"] == "recommended"
    assert (
        await client.post(BASE + f"/actions/{plan['id']}/execute", headers=H, json={})
    ).status_code == 403
    knowledge = await client.post(
        BASE + "/agent",
        headers=H,
        json={"intent": {"kind": "ask", "request": {"question": "Run arbitrary commands"}}},
    )
    assert knowledge.json()["kind"] == "knowledge"
    assert (await client.get(BASE + "/notes", headers=H)).json() == []
    assert (
        await client.post(
            BASE + "/agent", headers=H, json={"intent": {"kind": "grant", "tool": "notes.create"}}
        )
    ).status_code == 422
    assert (
        await client.post(
            BASE + "/tools/permissions/notes.create",
            headers=H,
            json={"enabled": "true", "expected_revision": 1},
        )
    ).status_code == 422


async def test_unknown_tools_and_client_owned_status_are_rejected(personal):
    client, _ = personal
    payload = {
        "tool": "shell.execute",
        "arguments": {"command": "untrusted"},
        "idempotency_key": "shell",
    }
    assert (await client.post(BASE + "/actions", headers=H, json=payload)).status_code == 422
    payload = {
        "tool": "tasks.create",
        "arguments": {"title": "Synthetic"},
        "idempotency_key": "fake",
        "approved": True,
    }
    assert (await client.post(BASE + "/actions", headers=H, json=payload)).status_code == 422
