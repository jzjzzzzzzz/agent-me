import copy
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.agency import Agency
from app.agency_models import PermissionInput, ToolInvocation
from app.audit import AuditLog
from app.consolidation import ConsolidationManager
from app.identity import IdentityStore
from app.learning import LearningPipeline
from app.learning_policy import LearningPolicyManager
from app.memory import (
    Entry,
    MemoryConflict,
    MemoryInputError,
    MemoryNotFound,
    MemoryPermissionDenied,
    Store,
)
from app.memory_models import (
    EntityInput,
    IngestionInput,
    LearningPolicy,
    MemoryExport,
    RelationshipInput,
    SourceInput,
)
from app.owner_control import OwnerControl
from app.portability import PortableMemory
from app.retention import RetentionManager


def seed(directory):
    db = Store(str(directory))
    identity = IdentityStore(db)
    person = identity.add(EntityInput(kind="person", name="Fictional Alex", aliases=["Alex"]))
    project = identity.add(EntityInput(kind="project", name="Fictional Orchid"))
    for item in [person, project]:
        identity.confirm(item["id"], 1)
    identity.bind_owner(person["id"])
    pipeline = LearningPipeline(db)
    source = pipeline.register(
        SourceInput(kind="document", name="Fictional notes", entity_id=person["id"])
    )
    pipeline.approve(source["id"])
    run = pipeline.ingest(
        source["id"],
        IngestionInput(
            content="fact profile.name: Fictional Alex\nfact project.role: Orchid builder"
        ),
    )
    for item in run["items"]:
        db.confirm(item["memory_id"], [], 1)
    edge = identity.relate(
        RelationshipInput(
            from_entity_id=person["id"],
            to_entity_id=project["id"],
            predicate="works_on",
            evidence_id=run["items"][1]["memory_id"],
        )
    )
    identity.confirm(edge["id"], 1, relationship=True)
    db.add(Entry(key="project.role", content="Orchid builder", entity_id=person["id"]))
    ConsolidationManager(db).preview()
    RetentionManager(db).preview()
    db.save_chat("Fictional transcript", "Fictional reply")
    forgotten = db.add(Entry(key="erased", content="Discarded fictional value"))
    db.delete(forgotten["id"])
    agency = Agency(db)
    agency.configure("notes.create", PermissionInput(enabled=True), 1)
    for key in ["executed", "approved"]:
        plan = agency.plan(
            ToolInvocation(
                tool="notes.create",
                arguments={"title": "Fictional note", "content": "Independent fictional copy"},
                idempotency_key=key,
            )
        )
        agency.approve(plan["id"], 1, plan["digest"])
        if key == "executed":
            agency.execute(plan["id"])
    return db, source["id"]


def test_reviewed_roundtrip_preserves_data_but_does_not_restore_authority(tmp_path):
    original, source_id = seed(tmp_path / "original")
    snapshot = original.export()
    destination = Store(str(tmp_path / "destination"))
    portable = PortableMemory(destination)
    preview = portable.preview(snapshot)
    assert not destination.entries() and not preview["tool_permissions_restored"]
    result = portable.apply(snapshot, preview["digest"])
    assert result["imported"] and destination.owner_id == original.owner_id
    before = MemoryExport.model_validate(snapshot).model_dump(mode="json")
    after = MemoryExport.model_validate(destination.export()).model_dump(mode="json")
    for key in [
        "entries",
        "revisions",
        "history",
        "entities",
        "entity_revisions",
        "relationships",
        "relationship_revisions",
        "origins",
        "forgotten",
        "ingestion_runs",
        "ingestion_replay_keys",
        "retention_policy",
        "learning_policy",
        "notes",
    ]:
        assert after[key] == before[key]
    assert after["owner_entity_id"] == before["owner_entity_id"]
    assert all(not item["approved"] for item in after["sources"])
    assert after["sources"][0]["revision"] == before["sources"][0]["revision"] + 1
    assert not after["action_plans"] and not after["action_events"]
    assert not after["retention_plans"] and not after["consolidation_plans"]
    assert all(not item["enabled"] for item in Agency(destination).permissions())
    archived = OwnerControl(destination).archives()[0]
    assert archived["id"] == result["archive_id"]
    assert archived["authority"]["action_plans"] == before["action_plans"]
    assert archived["authority"]["tool_permissions"] == before["tool_permissions"]
    with pytest.raises(MemoryPermissionDenied):
        LearningPipeline(destination).ingest(source_id, IngestionInput(content="fact a: New value"))
    old_approved = next(item for item in before["action_plans"] if item["status"] == "approved")
    with pytest.raises(MemoryNotFound):
        Agency(destination).execute(old_approved["id"])
    assert (
        destination.context("builder")
        and IdentityStore(destination).resolve("Alex")["status"] == "resolved"
    )
    # Another move keeps the previous immutable authority archive and remains inert.
    third = Store(str(tmp_path / "third"))
    second_snapshot = destination.export()
    second_preview = PortableMemory(third).preview(second_snapshot)
    PortableMemory(third).apply(second_snapshot, second_preview["digest"])
    assert len(OwnerControl(third).archives()) == 2 and not Agency(third).plans()


def test_import_review_digest_and_empty_destination_preconditions(tmp_path):
    original, _ = seed(tmp_path / "source")
    destination = Store(str(tmp_path / "dest"))
    importer = PortableMemory(destination)
    snapshot = original.export()
    preview = importer.preview(snapshot)
    before = destination.export()
    with pytest.raises(MemoryConflict, match="approval"):
        importer.apply(snapshot, "0" * 64)
    assert destination.export() == before
    changed = copy.deepcopy(snapshot)
    changed["history"][0]["content"] = "Changed fictional transcript"
    with pytest.raises(MemoryConflict):
        importer.apply(changed, preview["digest"])
    assert destination.export() == before
    destination.add(Entry(key="existing", content="Fictional keeper"))
    with pytest.raises(MemoryConflict, match="empty"):
        importer.apply(snapshot, preview["digest"])
    assert destination.entries()[0]["content"] == "Fictional keeper"
    configured = Store(str(tmp_path / "configured"))
    LearningPolicyManager(configured).configure(LearningPolicy(source_kinds=[]), 1)
    with pytest.raises(MemoryConflict, match="configured"):
        PortableMemory(configured).preview(snapshot)


def test_concurrent_import_commits_once_and_failure_rolls_back_adoption(tmp_path, monkeypatch):
    original, _ = seed(tmp_path / "source")
    snapshot = original.export()
    destination = Store(str(tmp_path / "dest"))
    importer = PortableMemory(destination)
    digest = importer.preview(snapshot)["digest"]
    before = destination.export()
    write = importer._write

    def fail_after_write(*args):
        write(*args)
        raise RuntimeError("Fictional private import failure")

    monkeypatch.setattr(importer, "_write", fail_after_write)
    with pytest.raises(RuntimeError):
        importer.apply(snapshot, digest)
    assert destination.export() == before
    monkeypatch.setattr(importer, "_write", write)

    def import_once(_):
        try:
            return importer.apply(snapshot, digest)["imported"]
        except MemoryConflict:
            return False

    with ThreadPoolExecutor(max_workers=3) as pool:
        assert list(pool.map(import_once, range(3))).count(True) == 1
    assert len(destination.entries(include_superseded=True)) == len(snapshot["entries"])


@pytest.mark.parametrize(
    "change",
    [
        "owner",
        "latest",
        "duplicate",
        "subject",
        "origin",
        "replay",
        "extra",
        "naive",
        "nan",
        "unicode",
        "version",
    ],
)
def test_malformed_snapshot_is_rejected_without_disclosure_or_writes(tmp_path, change):
    original, _ = seed(tmp_path / "source")
    snapshot = original.export()
    if change == "owner":
        snapshot["entries"][0]["owner_id"] = "unrelated-owner"
    elif change == "latest":
        snapshot["entries"][0]["content"] = "Fictional changed but no revision"
    elif change == "duplicate":
        snapshot["history"].append(snapshot["history"][0])
    elif change == "subject":
        snapshot["sources"][0]["entity_id"] = "missing-person"
    elif change == "origin":
        snapshot["origins"][0]["excerpt"] = "Fabricated fictional evidence"
    elif change == "replay":
        snapshot["ingestion_replay_keys"] = []
    elif change == "extra":
        snapshot["command"] = "undeclared execution capability"
    elif change == "naive":
        snapshot["history"][0]["created_at"] = "2020-01-01T00:00:00"
    elif change == "nan":
        snapshot["entries"][0]["confidence"] = float("nan")
    elif change == "unicode":
        snapshot["history"][0]["content"] = "\ud800"
    else:
        snapshot["version"] = 999
    destination = Store(str(tmp_path / "dest"))
    before = destination.export()
    with pytest.raises(MemoryInputError) as error:
        PortableMemory(destination).preview(snapshot)
    assert "Fabricated" not in str(error.value) and "Fictional" not in str(error.value)
    assert destination.export() == before


def test_version_six_import_and_bounded_count_and_byte_limits(tmp_path, monkeypatch):
    import app.portability as module

    original, _ = seed(tmp_path / "source")
    snapshot = original.export()
    snapshot["version"] = 6
    for key in ["audit_events", "import_archives", "ingestion_replay_keys", "disclosure_policy"]:
        del snapshot[key]
    destination = Store(str(tmp_path / "dest"))
    importer = PortableMemory(destination)
    preview = importer.preview(snapshot)
    assert preview["source_version"] == 6
    importer.apply(snapshot, preview["digest"])
    assert len(destination.export()["ingestion_replay_keys"]) == 1
    assert len(AuditLog(destination).events()) == 1
    monkeypatch.setattr(module, "MAX_COLLECTION", 1)
    with pytest.raises(MemoryInputError, match="counts"):
        PortableMemory(Store(str(tmp_path / "bounded"))).preview(original.export())
    monkeypatch.setattr(module, "MAX_IMPORT_BYTES", 100)
    with pytest.raises(MemoryInputError, match="16 MiB"):
        importer.preview(original.export())
    assert "Fictional" not in json.dumps(AuditLog(destination).events())


def test_version_seven_snapshot_gets_disabled_disclosure_defaults(tmp_path):
    source, _ = seed(tmp_path / "source")
    snapshot = source.export()
    snapshot["version"] = 7
    del snapshot["disclosure_policy"]
    destination = Store(str(tmp_path / "destination"))
    portable = PortableMemory(destination)
    preview = portable.preview(snapshot)
    assert preview["source_version"] == 7
    portable.apply(snapshot, preview["digest"])
    assert destination.export()["disclosure_policy"]["policy"]["enabled"] is False
