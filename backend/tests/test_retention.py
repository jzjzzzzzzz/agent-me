from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.learning import LearningPipeline
from app.memory import Entry, MemoryConflict, Store
from app.memory_models import IngestionInput, RetentionPolicy, SourceInput
from app.retention import RetentionManager

OLD = "2020-01-01T00:00:00+00:00"


def old_pending(db, key):
    item = db.add(Entry(key=key, content="SyntheticOrchid"))
    with db.connect() as connection:
        connection.execute("UPDATE entries SET updated_at=? WHERE id=?", (OLD, item["id"]))
        connection.execute("UPDATE revisions SET updated_at=? WHERE id=?", (OLD, item["id"]))
    return item


def test_retention_is_opt_in_previewed_atomic_and_idempotent(tmp_path):
    db = Store(str(tmp_path))
    manager = RetentionManager(db)
    item = old_pending(db, "project")
    assert manager.preview()["targets"] == []
    assert db.entries()
    manager.configure(RetentionPolicy(pending_days=1), 1)
    preview = manager.preview()
    assert preview["targets"] == [
        {"table": "entries", "id": item["id"], "revision": 1, "fingerprint": None}
    ]
    assert db.entries()
    result = manager.apply(preview["id"])
    assert result["deleted_counts"]["entries"] == 1 and result["status"] == "applied"
    assert not db.entries() and not db.export()["revisions"]
    assert db.export()["forgotten"]
    assert manager.apply(preview["id"]) == result
    source = LearningPipeline(db).register(SourceInput(kind="document", name="Synthetic"))
    LearningPipeline(db).approve(source["id"])
    run = LearningPipeline(db).ingest(
        source["id"], IngestionInput(content="fact project: SyntheticOrchid")
    )
    assert run["items"][0]["outcome"] == "forgotten"


def test_stale_policy_and_target_changes_never_partially_purge(tmp_path):
    db = Store(str(tmp_path))
    manager = RetentionManager(db)
    first = old_pending(db, "first")
    second = old_pending(db, "second")
    manager.configure(RetentionPolicy(pending_days=1), 1)
    preview = manager.preview()
    db.edit(second["id"], Entry(key="second", content="UpdatedCedar"), 1)
    with pytest.raises(MemoryConflict):
        manager.apply(preview["id"])
    assert {item["id"] for item in db.entries()} == {first["id"], second["id"]}
    preview = manager.preview()
    manager.configure(RetentionPolicy(), 2)
    with pytest.raises(MemoryConflict):
        manager.apply(preview["id"])
    assert len(db.entries()) == 2


def test_future_forecast_cannot_execute_early(tmp_path):
    db = Store(str(tmp_path))
    manager = RetentionManager(db)
    old_pending(db, "project")
    manager.configure(RetentionPolicy(pending_days=1), 1)
    preview = manager.preview(as_of=datetime.now(UTC) + timedelta(days=365))
    with pytest.raises(MemoryConflict, match="Future"):
        manager.apply(preview["id"])
    assert db.entries()


def test_retention_storage_failure_rolls_back_all_targets(tmp_path, monkeypatch):
    db = Store(str(tmp_path))
    manager = RetentionManager(db)
    old_pending(db, "first")
    old_pending(db, "second")
    manager.configure(RetentionPolicy(pending_days=1), 1)
    preview = manager.preview()
    before = db.export()
    original = db._delete
    calls = 0

    def fail_second(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Synthetic storage failure")
        original(*args)

    monkeypatch.setattr(db, "_delete", fail_second)
    with pytest.raises(RuntimeError):
        manager.apply(preview["id"])
    assert db.export() == before


def test_history_and_run_retention_preserve_memories_and_tombstones(tmp_path):
    db = Store(str(tmp_path))
    manager, pipeline = RetentionManager(db), LearningPipeline(db)
    db.save_chat("Synthetic question", "Synthetic answer")
    source = pipeline.register(SourceInput(kind="document", name="Synthetic"))
    pipeline.approve(source["id"])
    pipeline.ingest(source["id"], IngestionInput(content="fact project: SyntheticOrchid"))
    import json

    with db.connect() as connection:
        connection.execute("UPDATE turns SET created_at=?", (OLD,))
        row = connection.execute("SELECT id,run_json FROM ingestion_runs").fetchone()
        run = json.loads(row["run_json"])
        run["updated_at"] = OLD
        connection.execute(
            "UPDATE ingestion_runs SET run_json=? WHERE id=?", (json.dumps(run), row["id"])
        )
    manager.configure(RetentionPolicy(history_days=1, run_days=1), 1)
    preview = manager.preview()
    result = manager.apply(preview["id"])
    assert result["deleted_counts"] == {"entries": 0, "turns": 2, "ingestion_runs": 1}
    assert db.entries() and db.export()["origins"]
    assert not db.history() and not pipeline.runs()
    replay = pipeline.ingest(source["id"], IngestionInput(content="fact project: SyntheticOrchid"))
    assert replay["items"][0]["outcome"] == "duplicate"
    assert len(db.entries()) == 1


def test_expired_retention_is_separate_from_context_expiry(tmp_path):
    db = Store(str(tmp_path))
    manager = RetentionManager(db)
    item = db.add(Entry(key="project", content="ExpiredOrchid", valid_until=OLD))
    db.confirm(item["id"], [])
    assert not db.context("ExpiredOrchid") and db.entries()
    manager.configure(RetentionPolicy(expired_days=1), 1)
    preview = manager.preview()
    assert preview["targets"][0]["id"] == item["id"]
    manager.apply(preview["id"])
    assert not db.entries()


@pytest.mark.parametrize("value", [0, -1, True, "1", 1.2])
def test_retention_policy_requires_positive_integral_days(value):
    with pytest.raises(ValidationError):
        RetentionPolicy(pending_days=value)
