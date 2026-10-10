"""Real erasure graph/digest contracts on disposable fictional workspaces."""

import json
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.agency import Agency
from app.agency_models import PermissionInput, ToolInvocation
from app.erasure import ReviewedErasure
from app.erasure_models import ErasureApproval, ErasureRequest
from app.identity import IdentityStore
from app.learning import LearningPipeline
from app.memory import MemoryConflict, Store
from app.memory_models import EntityInput, Entry, IngestionInput, RelationshipInput, SourceInput
from app.owner_control import OwnerControl
from app.portability import PortableMemory


def tool(db, name="notes.create", sources=None, key="fictional-create"):
    agency = Agency(db)
    agency.configure(name, PermissionInput(enabled=True), 1)
    args = (
        {"title": "Fictional copy", "content": "UniqueFictionalPrivateBody"}
        if name == "notes.create"
        else {"title": "Fictional task", "description": "UniqueFictionalPrivateBody"}
    )
    plan = agency.plan(
        ToolInvocation(tool=name, arguments=args, source_ids=sources or [], idempotency_key=key)
    )
    agency.approve(plan["id"], 1, plan["digest"])
    return agency, agency.execute(plan["id"])


def request(db, kind, id, revision=None, **flags):
    return ErasureRequest(
        kind=kind, id=id, expected_owner_id=db.owner_id, expected_revision=revision, **flags
    )


def approve(preview):
    return ErasureApproval(request=preview.request, digest=preview.digest)


def counts(rows):
    return Counter(item.table for item in rows)


def source(db, name="Fictional registry", *, confirm=True):
    pipeline = LearningPipeline(db)
    source = pipeline.register(SourceInput(kind="document", name=name))
    source = pipeline.approve(source["id"], expected_revision=1)
    run = pipeline.ingest(
        source["id"], IngestionInput(content="fact project: UniqueFictionalPrivateBody")
    )
    memory = run["items"][0]["memory_id"]
    if confirm:
        db.confirm(memory, [], 1)
    return pipeline, source, memory


def test_preview_runs_real_deletion_but_leaves_all_state_and_audit_unchanged(tmp_path):
    db = Store(tmp_path)
    agency, plan = tool(db)
    manager = ReviewedErasure(db)
    before = db.export()
    preview = manager.preview(request(db, "note", plan["result"]["id"], 1))
    assert db.export() == before and preview.digest == manager.preview(preview.request).digest
    assert counts(preview.removed) == {"notes": 1, "action_plans": 1, "action_events": 4}
    assert not preview.added and not preview.updated and not preview.retained
    assert "UniqueFictionalPrivateBody" not in preview.model_dump_json()
    result = manager.apply(approve(preview))
    assert (
        result.removed_counts == counts(preview.removed)
        and not agency.notes()
        and not agency.plans()
    )
    assert "UniqueFictionalPrivateBody" not in json.dumps(db.export())


def test_output_scope_covers_associated_actions_beyond_latest_100_plan_ui_limit(tmp_path):
    db = Store(tmp_path)
    agency, original = tool(db, "tasks.create")
    agency.configure("tasks.complete", PermissionInput(enabled=True), 1)
    for n in range(105):
        agency.plan(
            ToolInvocation(
                tool="tasks.complete",
                arguments={"task_id": original["result"]["id"], "expected_revision": 1},
                idempotency_key=f"fictional-later-{n}",
            )
        )
    assert len(agency.plans()) == 100
    manager = ReviewedErasure(db)
    preview = manager.preview(request(db, "task", original["result"]["id"], 1))
    assert (
        counts(preview.removed)["action_plans"] == 106
        and counts(preview.removed)["action_events"] == 214
    )
    manager.apply(approve(preview))
    assert not agency.plans() and not agency.tasks()


@pytest.mark.parametrize("change", ["new_link", "event", "argument"])
def test_changed_cascading_action_scope_blocks_delete_without_partial_effects(tmp_path, change):
    db = Store(tmp_path)
    agency, plan = tool(db, "tasks.create")
    manager = ReviewedErasure(db)
    preview = manager.preview(request(db, "task", plan["result"]["id"], 1))
    if change == "new_link":
        agency.configure("tasks.complete", PermissionInput(enabled=True), 1)
        agency.plan(
            ToolInvocation(
                tool="tasks.complete",
                arguments={"task_id": plan["result"]["id"], "expected_revision": 1},
                idempotency_key="new-link",
            )
        )
    else:
        with db.connect() as connection:
            if change == "event":
                agency._event(
                    connection, plan["id"], "execution", "blocked", "fictional_new_receipt"
                )
            else:
                live = agency._object(connection, "action_plans", plan["id"])
                live["invocation"]["arguments"]["description"] = (
                    "Changed exact body without a revision"
                )
                agency._save_plan(connection, live)
    before = db.export()
    with pytest.raises(MemoryConflict, match="scope changed"):
        manager.apply(approve(preview))
    assert db.export() == before


def test_unrelated_data_changes_and_permission_revocation_do_not_block_owner_cleanup(tmp_path):
    db = Store(tmp_path)
    agency, plan = tool(db)
    manager = ReviewedErasure(db)
    preview = manager.preview(request(db, "note", plan["result"]["id"], 1))
    keep = db.add(Entry(key="unrelated", content="Fictional unrelated memory"))
    agency.configure("notes.create", PermissionInput(enabled=False), 2)
    manager.apply(approve(preview))
    assert not agency.notes() and db.entries()[0]["id"] == keep["id"]


@pytest.mark.parametrize("purge", [False, True])
def test_action_erasure_separately_reviews_current_output_not_old_execution_revision(
    tmp_path, purge
):
    db = Store(tmp_path)
    agency, plan = tool(db, "tasks.create")
    agency.configure("tasks.complete", PermissionInput(enabled=True), 1)
    complete = agency.plan(
        ToolInvocation(
            tool="tasks.complete",
            arguments={"task_id": plan["result"]["id"], "expected_revision": 1},
            idempotency_key="fictional-complete",
        )
    )
    agency.approve(complete["id"], 1, complete["digest"])
    agency.execute(complete["id"])
    manager = ReviewedErasure(db)
    preview = manager.preview(
        request(db, "action", plan["id"], plan["revision"], purge_output=purge)
    )
    assert preview.request.expected_output_revision == (2 if purge else None)
    assert counts(preview.removed)["tasks"] == int(purge)
    assert counts(preview.retained)["tasks"] == int(not purge)
    manager.apply(approve(preview))
    assert len(agency.tasks()) == int(not purge)
    assert len(agency.plans()) == int(not purge)


@pytest.mark.parametrize("forget", [False, True])
def test_source_scope_includes_restores_cross_source_origins_relationship_history_and_kept_tools(
    tmp_path, forget
):
    db = Store(tmp_path)
    pipeline, registry, memory = source(db, confirm=False)
    other = pipeline.register(SourceInput(kind="document", name="Other fictional source"))
    pipeline.approve(other["id"], expected_revision=1)
    pipeline.ingest(other["id"], IngestionInput(content="fact project: UniqueFictionalPrivateBody"))
    db.confirm(memory, [], next(row["revision"] for row in db.entries() if row["id"] == memory))
    restored = db.restore(memory, 1)
    identity = IdentityStore(db)
    entities = []
    for kind in ("person", "project"):
        item = identity.add(EntityInput(kind=kind, name=f"Fictional {kind}"))
        entities.append(identity.confirm(item["id"], 1))
    relation = identity.relate(
        RelationshipInput(
            from_entity_id=entities[0]["id"],
            to_entity_id=entities[1]["id"],
            predicate="works_on",
            evidence_id=memory,
        )
    )
    identity.confirm(relation["id"], 1, relationship=True)
    agency, _ = tool(db, sources=[memory])
    manager = ReviewedErasure(db)
    before = db.export()
    preview = manager.preview(request(db, "source", registry["id"], 2, forget_memories=forget))
    assert db.export() == before and preview.digest == manager.preview(preview.request).digest
    assert counts(preview.removed)["sources"] == 1
    assert counts(preview.removed)["entries"] == (2 if forget else 0)
    assert counts(preview.removed)["origins"] == (2 if forget else 1)
    assert counts(preview.removed)["relationships"] == int(forget)
    assert counts(preview.retained)["notes"] == counts(preview.retained)["action_plans"] == 1
    assert counts(preview.retained)["action_events"] == 4
    assert "UniqueFictionalPrivateBody" not in preview.model_dump_json()
    result = manager.apply(approve(preview))
    assert result.forgotten_memories == (2 if forget else 0)
    assert len(db.entries()) == (0 if forget else 2) and len(agency.notes()) == 1
    assert len(pipeline.sources()) == 1 and pipeline.sources()[0]["id"] == other["id"]
    assert len(identity.entities()) == 2
    assert any(item["id"] == restored["id"] for item in before["entries"])


@pytest.mark.parametrize("change", ["new_restore", "kept_note", "new_run_link"])
def test_source_graph_changes_in_removed_or_retained_copies_require_new_review(tmp_path, change):
    db = Store(tmp_path)
    pipeline, registry, memory = source(db)
    manager = ReviewedErasure(db)
    preview = manager.preview(request(db, "source", registry["id"], 2, forget_memories=True))
    if change == "new_restore":
        db.restore(memory, 1)
    elif change == "kept_note":
        tool(db, sources=[memory])
    else:
        other = pipeline.register(SourceInput(kind="document", name="New provenance"))
        pipeline.approve(other["id"], expected_revision=1)
        pipeline.ingest(
            other["id"], IngestionInput(content="fact project: UniqueFictionalPrivateBody")
        )
    before = db.export()
    with pytest.raises(MemoryConflict):
        manager.apply(approve(preview))
    assert db.export() == before


def test_inert_archive_authority_digest_binds_exact_body_without_erasing_live_import(tmp_path):
    original = Store(tmp_path / "original")
    tool(original)
    imported = Store(tmp_path / "imported")
    portable = PortableMemory(imported)
    result = portable.apply(original.export(), portable.preview(original.export())["digest"])
    manager = ReviewedErasure(imported)
    preview = manager.preview(request(imported, "archive", result["archive_id"]))
    assert counts(preview.removed) == {"import_archives": 1}
    with imported.connect() as db:
        row = db.execute(
            "SELECT data_json FROM import_archives WHERE id=?", (result["archive_id"],)
        ).fetchone()
        archive = json.loads(row[0])
        archive["authority"]["tool_permissions"] = []
        db.execute(
            "UPDATE import_archives SET data_json=? WHERE id=?",
            (json.dumps(archive), result["archive_id"]),
        )
    with pytest.raises(MemoryConflict):
        manager.apply(approve(preview))
    fresh = manager.preview(preview.request)
    manager.apply(approve(fresh))
    assert len(Agency(imported).notes()) == 1 and not OwnerControl(imported).archives()


def test_apply_failure_rolls_back_entire_scope_and_preview_receipts(tmp_path, monkeypatch):
    db = Store(tmp_path)
    _, plan = tool(db)
    manager = ReviewedErasure(db)
    preview = manager.preview(request(db, "note", plan["result"]["id"], 1))
    before = db.export()
    real = manager._apply
    calls = 0

    def fail(connection, payload):
        nonlocal calls
        calls += 1
        real(connection, payload)
        if calls == 2:
            raise RuntimeError("Fictional storage failure")
        return {"deleted": True}

    monkeypatch.setattr(manager, "_apply", fail)
    with pytest.raises(RuntimeError):
        manager.apply(approve(preview))
    assert db.export() == before


@pytest.mark.parametrize(
    "update",
    [
        {"expected_revision": None},
        {"expected_revision": True},
        {"expected_owner_id": ""},
        {"kind": "shell"},
        {"purge_output": True},
        {"forget_memories": True},
        {"expected_output_revision": 1},
        {"table": "arbitrary"},
        {"purge_output": "true"},
    ],
)
def test_erasure_inputs_reject_ambiguous_authority(update):
    with pytest.raises(ValidationError):
        ErasureRequest.model_validate(
            {
                "kind": "task",
                "id": "fictional",
                "expected_revision": 1,
                "expected_owner_id": "owner",
                **update,
            }
        )


async def test_authenticated_api_scope_preview_and_apply_redact_content_and_require_current_digest(
    personal,
):
    client, settings = personal
    db = Store(settings.personal_data_dir)
    agency, plan = tool(db)
    payload = request(db, "note", plan["result"]["id"], 1).model_dump(mode="json")
    assert (
        await client.post("/api/v1/personal/owner/erasure/preview", json=payload)
    ).status_code == 401
    headers = {"Authorization": f"Bearer {settings.personal_token}"}
    preview = await client.post(
        "/api/v1/personal/owner/erasure/preview", headers=headers, json=payload
    )
    assert preview.status_code == 200 and preview.headers["cache-control"] == "no-store"
    assert "UniqueFictionalPrivateBody" not in preview.text
    approval = {"request": preview.json()["request"], "digest": "0" * 64}
    assert (
        await client.post("/api/v1/personal/owner/erasure/apply", headers=headers, json=approval)
    ).status_code == 409
    assert len(agency.notes()) == 1
    approval["digest"] = preview.json()["digest"]
    assert (
        await client.post("/api/v1/personal/owner/erasure/apply", headers=headers, json=approval)
    ).status_code == 200
    assert not agency.notes() and not agency.plans()


def test_catalogue_is_snapshot_consistent_metadata_without_private_arguments(tmp_path):
    db = Store(tmp_path)
    tool(db)
    _, registered, _ = source(db)
    catalogue = ReviewedErasure(db).catalogue()
    assert catalogue.owner_id == db.owner_id
    assert {item.kind for item in catalogue.items} == {"note", "action", "source"}
    assert (
        next(item.record.revision for item in catalogue.items if item.record.id == registered["id"])
        == 2
    )
    assert "UniqueFictionalPrivateBody" not in catalogue.model_dump_json()


def test_existing_forgetting_hash_update_is_stable_even_when_the_clock_equals_old_timestamp(
    tmp_path, monkeypatch
):
    from app import memory as memory_module
    from app.memory import record_digest

    db = Store(tmp_path)
    _, registry, memory = source(db)
    frozen = datetime(2026, 10, 1, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen

    monkeypatch.setattr(memory_module, "datetime", Clock)
    row = db.revisions(memory)[0]
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO forgotten VALUES (?,?)", (record_digest(row), frozen.isoformat())
        )
    manager = ReviewedErasure(db)
    preview = manager.preview(request(db, "source", registry["id"], 2, forget_memories=True))
    assert counts(preview.updated)["forgotten"] == 1
    frozen += timedelta(seconds=1)
    assert manager.preview(preview.request).digest == preview.digest
    manager.apply(approve(preview))
    assert not db.entries()


@pytest.mark.parametrize("forget", [False, True])
def test_cli_erasure_requires_exact_scope_and_yes_without_http_or_provider(
    tmp_path, capsys, forget
):
    from app.agent_cli import main

    db = Store(tmp_path / "workspace")
    pipeline, registry, _ = source(db)
    file = tmp_path / "request.json"
    payload = request(db, "source", registry["id"], 2, forget_memories=forget)
    file.write_text(payload.model_dump_json(), encoding="utf-8")
    prefix = ["--data-dir", str(db.root), "owner"]
    assert main([*prefix, "preview-erasure", str(file)]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert "UniqueFictionalPrivateBody" not in json.dumps(preview)
    assert main([*prefix, "apply-erasure", str(file), "--digest", preview["digest"]]) == 2
    capsys.readouterr()
    assert main([*prefix, "apply-erasure", str(file), "--digest", "0" * 64, "--yes"]) == 2
    capsys.readouterr()
    assert len(pipeline.sources()) == 1
    assert main([*prefix, "apply-erasure", str(file), "--digest", preview["digest"], "--yes"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["forgotten_memories"] == int(forget) and not pipeline.sources()
    assert len(db.entries()) == int(not forget)
