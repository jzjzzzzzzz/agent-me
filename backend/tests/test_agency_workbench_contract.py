import json
from pathlib import Path

import pytest

from app.agency import Agency
from app.agency_models import (
    ActionEvent,
    ActionPlan,
    NoteRecord,
    PermissionInput,
    TaskRecord,
    ToolInvocation,
    ToolPermission,
)
from app.memory import MemoryInputError, Store
from app.memory_models import Entry


def test_shared_fictional_workbench_fixtures_obey_native_contracts():
    file = Path(__file__).resolve().parents[2] / "frontend/src/__fixtures__/agency.json"
    payload = json.loads(file.read_text(encoding="utf-8"))
    for key in (
        "planned",
        "approved",
        "completed",
        "completionPlan",
        "completion",
        "rolledBack",
        "recommended",
        "cancelled",
        "notePlan",
        "noteCompleted",
        "failed",
    ):
        plan = ActionPlan.model_validate(payload[key])
        assert plan.owner_id == payload["owner_id"]
    for key, model in (
        ("disabled", ToolPermission),
        ("permissions", ToolPermission),
        ("tasks", TaskRecord),
        ("notes", NoteRecord),
        ("events", ActionEvent),
    ):
        for row in payload[key]:
            model.model_validate(row)


@pytest.mark.parametrize("intent", ["act", "recommend"])
def test_completion_source_union_cannot_persist_an_unserializable_over_limit_plan(tmp_path, intent):
    db = Store(tmp_path)
    agency = Agency(db)
    agency.configure("tasks.create", PermissionInput(enabled=True), 1)
    agency.configure("tasks.complete", PermissionInput(enabled=True), 1)
    sources = []
    for n in range(21):
        entry = db.add(Entry(key=f"fictional.source.{n}", content=f"Fictional evidence {n}"))
        db.confirm(entry["id"], [], 1)
        sources.append(entry["id"])
    plan = agency.plan(
        ToolInvocation(
            tool="tasks.create",
            arguments={"title": "Fictional lineage limit"},
            source_ids=sources[:20],
            idempotency_key="limit-create",
        )
    )
    agency.approve(plan["id"], 1, plan["digest"])
    result = agency.execute(plan["id"])
    task = agency.tasks()[0]
    before = agency.plans()
    with pytest.raises(MemoryInputError, match="Combined action sources"):
        agency.plan(
            ToolInvocation(
                tool="tasks.complete",
                arguments={"task_id": result["result"]["id"], "expected_revision": 1},
                source_ids=[sources[20]],
                intent=intent,
                idempotency_key="limit-update",
            )
        )
    assert agency.plans() == before and agency.tasks() == [task]
    valid = agency.plan(
        ToolInvocation(
            tool="tasks.complete",
            arguments={"task_id": task["id"], "expected_revision": 1},
            source_ids=[sources[0]],
            intent=intent,
            idempotency_key="limit-valid",
        )
    )
    assert len(valid["invocation"]["source_ids"]) == 20
    ActionPlan.model_validate(valid)


async def test_api_over_limit_inherited_source_union_is_rejected_before_plan_commit(personal):
    client, settings = personal
    db = Store(settings.personal_data_dir)
    agency = Agency(db)
    agency.configure("tasks.create", PermissionInput(enabled=True), 1)
    agency.configure("tasks.complete", PermissionInput(enabled=True), 1)
    sources = []
    for n in range(21):
        entry = db.add(Entry(key=f"fictional.api.{n}", content=f"Fictional API evidence {n}"))
        db.confirm(entry["id"], [], 1)
        sources.append(entry["id"])
    original = agency.plan(
        ToolInvocation(
            tool="tasks.create",
            arguments={"title": "Fictional API lineage"},
            source_ids=sources[:20],
            idempotency_key="api-source-create",
        )
    )
    agency.approve(original["id"], 1, original["digest"])
    completed = agency.execute(original["id"])
    before = agency.plans()
    headers = {"Authorization": f"Bearer {settings.personal_token}"}
    payload = {
        "tool": "tasks.complete",
        "arguments": {"task_id": completed["result"]["id"], "expected_revision": 1},
        "source_ids": [sources[20]],
        "idempotency_key": "api-source-limit",
    }
    response = await client.post("/api/v1/personal/actions", headers=headers, json=payload)
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert "Combined action sources" in response.json()["detail"]
    assert agency.plans() == before and agency.tasks()[0]["revision"] == 1
    payload.update(source_ids=[sources[0]], idempotency_key="api-source-valid")
    response = await client.post("/api/v1/personal/actions", headers=headers, json=payload)
    assert response.status_code == 200
    assert len(ActionPlan.model_validate(response.json()).invocation.source_ids) == 20


async def test_reviewed_tool_permission_owner_precondition_survives_workspace_revision_reset(
    personal,
):
    from app.owner_control import OwnerControl
    from app.owner_models import WorkspacePurge

    client, settings = personal
    db = Store(settings.personal_data_dir)
    agency = Agency(db)
    reviewed = agency.permissions()[0]
    OwnerControl(db).purge(
        WorkspacePurge(
            expected_owner_id=reviewed["owner_id"],
            confirmation="erase-personal-workspace",
        )
    )
    current = agency.permissions()[0]
    assert (
        current["owner_id"] != reviewed["owner_id"]
        and current["revision"] == reviewed["revision"] == 1
    )
    headers = {"Authorization": f"Bearer {settings.personal_token}"}
    payload = {"enabled": True, "expected_revision": 1, "expected_owner_id": reviewed["owner_id"]}
    response = await client.post(
        "/api/v1/personal/tools/permissions/tasks.create", headers=headers, json=payload
    )
    assert response.status_code == 409 and agency.permissions() == [
        current,
        *agency.permissions()[1:],
    ]
    assert not current["enabled"] and not agency.permissions()[0]["enabled"]
    payload["expected_owner_id"] = current["owner_id"]
    response = await client.post(
        "/api/v1/personal/tools/permissions/tasks.create", headers=headers, json=payload
    )
    assert (
        response.status_code == 200
        and response.json()["enabled"]
        and response.json()["revision"] == 2
    )
    assert "expected_owner_id" not in response.json()
    # Existing native/CLI/API clients may intentionally omit this additive review precondition.
    response = await client.post(
        "/api/v1/personal/tools/permissions/tasks.create",
        headers=headers,
        json={"enabled": False, "expected_revision": 2},
    )
    assert response.status_code == 200 and not response.json()["enabled"]
