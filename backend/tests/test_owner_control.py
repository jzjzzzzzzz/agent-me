import json

import pytest
from pydantic import ValidationError

from app.agency import Agency
from app.agency_models import PermissionInput, ToolInvocation
from app.audit import AuditLog
from app.learning import LearningPipeline
from app.memory import (
    MemoryConflict,
    MemoryInputError,
    MemoryNotFound,
    MemoryPermissionDenied,
    Store,
)
from app.memory_models import IngestionInput, MemoryExport, SourceInput
from app.owner_control import OwnerControl
from app.owner_models import WorkspacePurge
from app.portability import PortableMemory
from app.retrieval import PersonalRetriever
from app.retrieval_models import AskRequest


def created_note(db):
    agency = Agency(db)
    agency.configure("notes.create", PermissionInput(enabled=True), 1)
    plan = agency.plan(
        ToolInvocation(
            tool="notes.create",
            arguments={"title": "Fictional note", "content": "FictionalSensitiveCopy"},
            idempotency_key="create",
        )
    )
    agency.approve(plan["id"], 1, plan["digest"])
    result = agency.execute(plan["id"])
    return agency, result


def source_memory(db):
    pipeline = LearningPipeline(db)
    source = pipeline.register(SourceInput(kind="document", name="Fictional source"))
    pipeline.approve(source["id"])
    run = pipeline.ingest(source["id"], IngestionInput(content="fact project: FictionalOrchid"))
    return pipeline, source["id"], run["items"][0]["memory_id"]


def test_output_erasure_is_revision_bound_and_removes_related_plan_copies(tmp_path):
    db = Store(str(tmp_path))
    agency, plan = created_note(db)
    owner = OwnerControl(db)
    with pytest.raises(MemoryConflict):
        owner.delete_output("notes", plan["result"]["id"], 99)
    assert len(agency.notes()) == len(agency.plans()) == 1
    owner.delete_output("notes", plan["result"]["id"], 1)
    snapshot = db.export()
    assert not snapshot["notes"] and not snapshot["action_plans"] and not snapshot["action_events"]
    assert "FictionalSensitiveCopy" not in json.dumps(snapshot)
    with pytest.raises(MemoryInputError):
        owner.delete_output("arbitrary_table", "id", 1)


def test_action_record_erasure_does_not_implicitly_erase_independent_output(tmp_path):
    db = Store(str(tmp_path))
    agency, plan = created_note(db)
    owner = OwnerControl(db)
    owner.delete_action(plan["id"], plan["revision"])
    assert not agency.plans() and len(agency.notes()) == 1
    owner.delete_output("notes", plan["result"]["id"], 1)
    assert not agency.notes()


def test_action_output_erasure_requires_current_output_review(tmp_path):
    db = Store(str(tmp_path))
    agency, plan = created_note(db)
    owner = OwnerControl(db)
    with pytest.raises(MemoryConflict):
        owner.delete_action(
            plan["id"], plan["revision"], purge_output=True, expected_output_revision=9
        )
    assert len(agency.plans()) == len(agency.notes()) == 1
    owner.delete_action(plan["id"], plan["revision"], purge_output=True, expected_output_revision=1)
    assert not agency.plans() and not agency.notes()


@pytest.mark.parametrize("forget", [False, True])
def test_source_erasure_explicitly_controls_derived_and_restored_memories(tmp_path, forget):
    db = Store(str(tmp_path))
    pipeline, source_id, memory_id = source_memory(db)
    db.confirm(memory_id, [], 1)
    restored = db.restore(memory_id, 1)
    assert len(db.entries()) == 2
    owner = OwnerControl(db)
    before = db.export()
    with pytest.raises(MemoryConflict):
        owner.delete_source(source_id, 1, forget_memories=forget)
    assert db.export() == before
    result = owner.delete_source(source_id, 2, forget_memories=forget)
    assert result["forgotten_memories"] == (2 if forget else 0)
    snapshot = db.export()
    assert not snapshot["sources"] and not snapshot["origins"] and not snapshot["ingestion_runs"]
    assert not snapshot["ingestion_replay_keys"]
    assert len(snapshot["entries"]) == (0 if forget else 2)
    if forget:
        assert snapshot["forgotten"] and not db.context("FictionalOrchid")
        with pytest.raises(MemoryNotFound):
            pipeline.origins(restored["id"])


def test_workspace_purge_erases_all_sqlite_copies_and_resets_authority(tmp_path):
    original = Store(str(tmp_path / "original"))
    created_note(original)
    _, _, memory_id = source_memory(original)
    original.confirm(memory_id, [], 1)
    original.save_chat("FictionalSensitiveCopy", "Fictional answer")
    target = Store(str(tmp_path / "target"))
    snapshot = original.export()
    preview = PortableMemory(target).preview(snapshot)
    PortableMemory(target).apply(snapshot, preview["digest"])
    owner = OwnerControl(target)
    original_owner = target.owner_id
    with pytest.raises(MemoryConflict):
        owner.purge(
            WorkspacePurge(
                expected_owner_id="different-owner", confirmation="erase-personal-workspace"
            )
        )
    result = owner.purge(
        WorkspacePurge(expected_owner_id=original_owner, confirmation="erase-personal-workspace")
    )
    assert result["owner_id"] != original_owner
    erased = MemoryExport.model_validate(target.export()).model_dump(mode="json")
    assert all(
        not value
        for key, value in erased.items()
        if isinstance(value, list) and key != "audit_events"
    )
    assert (
        len(erased["audit_events"]) == 1
        and erased["audit_events"][0]["operation"] == "owner.workspace_purge"
    )
    assert "FictionalSensitiveCopy" not in json.dumps(erased)
    assert all(not item["enabled"] for item in Agency(target).permissions())
    assert erased["learning_policy"]["revision"] == erased["retention_policy"]["revision"] == 1
    assert PortableMemory(target).preview(snapshot)


def test_archive_can_be_erased_without_changing_imported_memory(tmp_path):
    original = Store(str(tmp_path / "original"))
    created_note(original)
    target = Store(str(tmp_path / "target"))
    portable = PortableMemory(target)
    snapshot = original.export()
    result = portable.apply(snapshot, portable.preview(snapshot)["digest"])
    OwnerControl(target).delete_archive(result["archive_id"])
    assert not OwnerControl(target).archives() and len(Agency(target).notes()) == 1
    with pytest.raises(MemoryNotFound):
        OwnerControl(target).delete_archive(result["archive_id"])


def test_core_ingestion_and_retrieval_audit_is_content_free_and_bounded(tmp_path):
    db = Store(str(tmp_path))
    pipeline, source_id, memory_id = source_memory(db)
    db.confirm(memory_id, [], 1)
    pipeline.ingest(source_id, IngestionInput(content="fact project: FictionalOrchid"))
    PersonalRetriever(db).retrieve(AskRequest(question="UniquePrivateQuestionFictionalOrchid"))
    pipeline.approve(source_id, approved=False)
    with pytest.raises(MemoryPermissionDenied):
        pipeline.ingest(source_id, IngestionInput(content="fact private: UniquePrivateDocument"))
    events = AuditLog(db).events(100)
    assert {item["operation"] for item in events} >= {
        "learning.ingest",
        "learning.replay",
        "retrieval.retrieve",
    }
    assert any(item["outcome"] == "denied" for item in events)
    assert all(item["owner_id"] == db.owner_id for item in events)
    for value in ["UniquePrivateQuestion", "UniquePrivateDocument", "FictionalOrchid"]:
        assert value not in json.dumps(events)
    with pytest.raises(MemoryInputError):
        AuditLog(db).events(1001)
    with pytest.raises(ValidationError):
        AuditLog(db).record("arbitrary private text")
    with pytest.raises(ValidationError):
        AuditLog(db).record("valid.operation", counts={"secret body": 1})
    AuditLog(db).clear()
    assert [item["operation"] for item in AuditLog(db).events()] == ["audit.clear"]


def test_operational_audit_rotates_at_ten_thousand_records(tmp_path):
    db = Store(str(tmp_path))
    owner_id = db.owner_id
    with db.connect() as connection:
        connection.executemany(
            "INSERT INTO audit_events VALUES (?,?)",
            [
                (
                    f"old-{index}",
                    json.dumps(
                        {
                            "id": f"old-{index}",
                            "owner_id": owner_id,
                            "actor": "core",
                            "operation": "fixture.access",
                            "outcome": "succeeded",
                            "counts": {},
                            "created_at": "2020-01-01T00:00:00Z",
                        }
                    ),
                )
                for index in range(10005)
            ],
        )
    AuditLog(db).record("audit.rotation")
    with db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 10000
        assert not connection.execute("SELECT 1 FROM audit_events WHERE id='old-5'").fetchone()
    assert AuditLog(db).events(1)[0]["operation"] == "audit.rotation"
