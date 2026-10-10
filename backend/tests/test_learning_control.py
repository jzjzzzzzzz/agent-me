import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.agency import Agency
from app.agency_models import PermissionInput, ToolInvocation
from app.consolidation import ConsolidationManager
from app.identity import IdentityStore
from app.learning import LearningPipeline
from app.learning_policy import LearningPolicyManager
from app.memory import Entry, MemoryConflict, MemoryPermissionDenied, Store
from app.memory_models import (
    ConsolidationFilter,
    EntityInput,
    IngestionInput,
    LearningPolicy,
    MemoryExport,
    SourceInput,
)


def approved_source(db, **kwargs):
    pipeline = LearningPipeline(db)
    source = pipeline.register(SourceInput(kind="document", name="Fictional control", **kwargs))
    pipeline.approve(source["id"])
    return pipeline, source["id"]


def test_version_five_upgrade_preserves_reviewed_memory_and_tool_authority(tmp_path):
    db = Store(str(tmp_path))
    memory = db.add(Entry(key="project", content="Fictional Orchid"))
    db.confirm(memory["id"], [])
    agency = Agency(db)
    agency.configure("tasks.create", PermissionInput(enabled=True), 1)
    plan = agency.plan(
        ToolInvocation(
            tool="tasks.create", arguments={"title": "Fictional task"}, idempotency_key="migration"
        )
    )
    agency.approve(plan["id"], 1, plan["digest"])
    with sqlite3.connect(db.path) as connection:
        connection.execute("DROP TABLE consolidation_plans")
        connection.execute(
            "DELETE FROM workspace WHERE key IN ('learning_policy','learning_revision')"
        )
        connection.execute("PRAGMA user_version=5")
    reopened = Store(str(tmp_path))
    assert reopened.owner_id == db.owner_id and reopened.context("Orchid")
    assert reopened.export()["version"] == 7
    assert LearningPolicyManager(reopened).settings()["revision"] == 1
    assert Agency(reopened).execute(plan["id"])["status"] == "completed"
    assert len(Agency(reopened).tasks()) == 1


def test_policy_scope_limits_and_completed_replay_remain_explicit(tmp_path):
    db = Store(str(tmp_path))
    pipeline, source_id = approved_source(db)
    manager = LearningPolicyManager(db)
    assert manager.settings()["policy"]["max_candidates"] == 100
    manager.configure(LearningPolicy(source_kinds=[]), 1)
    with pytest.raises(MemoryPermissionDenied):
        pipeline.ingest(source_id, IngestionInput(content="fact project: Fictional Orchid"))
    assert not pipeline.runs() and not db.entries()
    with pytest.raises(MemoryConflict):
        manager.configure(LearningPolicy(), 1)
    manager.configure(LearningPolicy(labels=["public"]), 2)
    with pytest.raises(MemoryPermissionDenied):
        pipeline.ingest(source_id, IngestionInput(content="fact project: Fictional Orchid"))
    manager.configure(LearningPolicy(max_candidates=1), 3)
    payload = IngestionInput(content="fact a: Fictional Orchid\nfact b: Fictional Cedar")
    failure = pipeline.ingest(source_id, payload)
    assert failure["status"] == "failed" and failure["error_code"] == "extraction_invalid"
    assert not db.entries()
    manager.configure(LearningPolicy(), 4)
    retried = pipeline.ingest(source_id, payload)
    assert retried["id"] == failure["id"] and retried["attempts"] == 2
    assert all(item["status"] == "pending" for item in db.entries())
    manager.configure(LearningPolicy(source_kinds=[]), 5)
    with pytest.raises(MemoryPermissionDenied):
        pipeline.ingest(source_id, payload)  # Policy also gates returning a completed replay.


def test_blocked_identity_prefix_is_unicode_case_aware_and_atomic(tmp_path):
    db = Store(str(tmp_path))
    pipeline, source_id = approved_source(db)
    LearningPolicyManager(db).configure(LearningPolicy(blocked_key_prefixes=["IDENTITY."]), 1)
    result = pipeline.ingest(
        source_id, IngestionInput(content="fact safe: Fictional Cedar\nfact identity.name: Example")
    )
    assert result["status"] == "failed" and not db.entries()
    assert "Fictional Cedar" not in json.dumps(pipeline.runs())


def test_sensitive_and_identity_review_can_require_full_revision_preconditions(tmp_path):
    db = Store(str(tmp_path))
    LearningPolicyManager(db).configure(
        LearningPolicy(
            require_revision_labels=["sensitive"], require_revision_key_prefixes=["PROFILE."]
        ),
        1,
    )
    item = db.add(Entry(key="profile.name", content="Fictional Example"))
    with pytest.raises(MemoryPermissionDenied, match="revision-bound"):
        db.confirm(item["id"], [])
    db.confirm(item["id"], [], 1)
    updated = db.add(Entry(key="profile.name", content="Fictional New Example"))
    with pytest.raises(MemoryPermissionDenied, match="replacement"):
        db.confirm(updated["id"], [item["id"]], 1)
    db.confirm(updated["id"], [item["id"]], 1, {item["id"]: 2})
    secret = db.add(Entry(key="preference", content="Fictional secret", sensitivity="sensitive"))
    with pytest.raises(MemoryPermissionDenied):
        db.confirm(secret["id"], [])
    db.confirm(secret["id"], [], 1)


def test_live_entity_privacy_cannot_bypass_strict_review_policy(tmp_path):
    db = Store(str(tmp_path))
    identity = IdentityStore(db)
    person = identity.add(EntityInput(kind="person", name="Fictional Example"))
    identity.confirm(person["id"], 1)
    memory = db.add(Entry(key="name", content="Fictional Example", entity_id=person["id"]))
    identity.edit(
        person["id"],
        EntityInput(kind="person", name="Fictional Example", sensitivity="sensitive"),
        2,
    )
    identity.confirm(person["id"], 3)
    LearningPolicyManager(db).configure(LearningPolicy(require_revision_labels=["sensitive"]), 1)
    with pytest.raises(MemoryPermissionDenied):
        db.confirm(memory["id"], [])
    db.confirm(memory["id"], [], 1)


def test_consolidation_is_reviewed_idempotent_and_preserves_origins_and_history(tmp_path):
    db = Store(str(tmp_path))
    pipeline, source_id = approved_source(db)
    learned = pipeline.ingest(source_id, IngestionInput(content="fact project: Fictional Orchid"))
    candidate_id = learned["items"][0]["memory_id"]
    keeper = db.add(Entry(key="project", content="Fictional Orchid"))
    db.confirm(keeper["id"], [])
    manager = ConsolidationManager(db)
    plan = manager.preview()
    assert len(plan["groups"]) == 1 and plan["groups"][0]["keeper_id"] == keeper["id"]
    assert len(db.entries()) == 2  # Preview has no effects.
    with pytest.raises(MemoryConflict, match="approval"):
        manager.apply(plan["id"], "0" * 64)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: manager.apply(plan["id"], plan["digest"]), range(3)))
    assert all(result == results[0] for result in results)
    assert results[0]["merged_count"] == 1
    assert len(db.entries()) == 1 and len(db.entries(include_superseded=True)) == 2
    assert db.revisions(candidate_id)[-1]["change"] == "superseded"
    assert db.revisions(keeper["id"])[-1]["change"] == "corroborated"
    origins = pipeline.origins(keeper["id"])
    assert origins[0]["excerpt"] == "Fictional Orchid" and origins[0]["source_id"] == source_id
    assert origins[0]["memory_revision"] == 3
    assert db.context("Orchid") and MemoryExport.model_validate(db.export()).version == 7


def test_pending_consolidation_is_never_auto_confirmation(tmp_path):
    db = Store(str(tmp_path))
    for _ in range(3):
        db.add(Entry(key="project", content="Fictional Orchid"))
    manager = ConsolidationManager(db)
    plan = manager.preview()
    assert manager.apply(plan["id"], plan["digest"])["merged_count"] == 2
    assert db.entries()[0]["status"] == "pending" and not db.context("Orchid")


@pytest.mark.parametrize("change", ["edit", "delete", "review"])
def test_stale_consolidation_never_partially_applies(tmp_path, change):
    db = Store(str(tmp_path))
    items = [db.add(Entry(key="project", content="Fictional Orchid")) for _ in range(2)]
    manager = ConsolidationManager(db)
    plan = manager.preview()
    if change == "edit":
        db.edit(items[1]["id"], Entry(key="project", content="Fictional Cedar"), 1)
    elif change == "delete":
        db.delete(items[1]["id"])
    else:
        db.confirm(items[1]["id"], [], 1)
    before = db.export()
    with pytest.raises(MemoryConflict, match="changed"):
        manager.apply(plan["id"], plan["digest"])
    assert db.export() == before


def test_failed_consolidation_rolls_back_all_groups(tmp_path, monkeypatch):
    db = Store(str(tmp_path))
    for key in ["a", "b"]:
        for _ in range(2):
            db.add(Entry(key=key, content="Fictional Orchid"))
    manager = ConsolidationManager(db)
    plan = manager.preview()
    original = db._snapshot
    count = 0

    def failing_snapshot(connection, entry_id, change):
        nonlocal count
        count += 1
        original(connection, entry_id, change)
        if count == 3:
            raise RuntimeError("Fictional failure")

    monkeypatch.setattr(db, "_snapshot", failing_snapshot)
    before = db.export()
    with pytest.raises(RuntimeError):
        manager.apply(plan["id"], plan["digest"])
    assert db.export() == before


def test_distinct_qualifiers_are_not_semantically_consolidated(tmp_path):
    db = Store(str(tmp_path))
    for fields in [
        {},
        {"sensitivity": "sensitive"},
        {"confidence": 0.5},
        {"belief": "inferred"},
        {"valid_until": "2020-01-01T00:00:00Z"},
        {"content": "Fictional Cedar"},
    ]:
        db.add(Entry(**{"key": "project", "content": "Fictional Orchid", **fields}))
    assert ConsolidationManager(db).preview()["groups"] == []


def test_owner_can_narrow_consolidation_without_touching_other_groups(tmp_path):
    db = Store(str(tmp_path))
    for key in ["project.a", "project.b"]:
        for _ in range(2):
            db.add(Entry(key=key, content="Fictional Orchid"))
    manager = ConsolidationManager(db)
    plan = manager.preview(ConsolidationFilter(key_prefix="PROJECT.A", kinds=["fact"]))
    assert len(plan["groups"]) == 1
    manager.apply(plan["id"], plan["digest"])
    assert len(db.entries()) == 3
    assert manager.preview(ConsolidationFilter(kinds=[]))["groups"] == []
    assert manager.preview(ConsolidationFilter(entity_id="unrelated-owner-entity"))["groups"] == []
