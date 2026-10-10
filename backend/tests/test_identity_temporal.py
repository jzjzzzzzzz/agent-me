import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.identity import IdentityStore
from app.learning import LearningPipeline
from app.memory import Entry, MemoryConflict, MemoryNotFound, Store
from app.memory_models import (
    EntityInput,
    IngestionInput,
    MemoryExport,
    RelationshipInput,
    SourceInput,
    TemporalQuery,
)


def entity(identity, kind, name, **extra):
    item = identity.add(EntityInput(kind=kind, name=name, **extra))
    return identity.confirm(item["id"], 1)


def test_identity_review_alias_deduplication_ambiguity_and_owner(tmp_path):
    db = Store(str(tmp_path))
    identity = IdentityStore(db)
    pending = identity.add(EntityInput(kind="person", name="Alex Example", aliases=["Alex"]))
    assert identity.resolve("Alex")["status"] == "unknown"
    assert (
        identity.add(EntityInput(kind="person", name="ALEX EXAMPLE", aliases=["alex"]))["id"]
        == pending["id"]
    )
    known = identity.confirm(pending["id"], 1)
    assert identity.resolve(" alex ")["matches"] == [known]
    other = identity.add(EntityInput(kind="person", name="Alex Different", aliases=["Alex"]))
    identity.confirm(other["id"], 1)
    assert identity.resolve("Alex")["status"] == "ambiguous"
    assert identity.resolve("Alex Example")["status"] == "resolved"
    assert known["owner_id"] == db.owner_id == Store(str(tmp_path)).owner_id
    assert [row["change"] for row in identity.history(pending["id"])] == ["created", "confirmed"]


def test_linked_memory_scopes_and_source_alias_resolution(tmp_path):
    db = Store(str(tmp_path))
    identity, learning = IdentityStore(db), LearningPipeline(db)
    alex = entity(identity, "person", "Alex Example", aliases=["Alex"])
    bob = entity(identity, "person", "Bob Example")
    one = db.add(Entry(key="role", content="Engineer", entity_id=alex["id"]))
    two = db.add(Entry(key="role", content="Designer", entity_id=bob["id"]))
    db.confirm(one["id"], [])
    db.confirm(two["id"], [])  # Same key is not a contradiction across different subjects.
    assert db.context("Engineer", entity_id=alex["id"])
    assert not db.context("Designer", entity_id=alex["id"])
    source = learning.register(
        SourceInput(kind="document", name="Synthetic profile", entity_alias="Alex")
    )
    assert source["entity_id"] == alex["id"]
    learning.approve(source["id"])
    run = learning.ingest(source["id"], IngestionInput(content="fact role: Engineer"))
    assert run["items"][0]["outcome"] == "known"
    assert MemoryExport.model_validate(db.export()).entities[0].owner_id == db.owner_id
    with pytest.raises(MemoryNotFound):
        db.add(Entry(key="role", content="Unknown", entity_id="missing"))
    pending = identity.add(EntityInput(kind="person", name="Unconfirmed"))
    with pytest.raises(MemoryConflict):
        db.add(Entry(key="role", content="Unknown", entity_id=pending["id"]))


def test_relationships_need_review_and_fresh_confirmed_evidence(tmp_path):
    db = Store(str(tmp_path))
    identity = IdentityStore(db)
    alex = entity(identity, "person", "Alex Example")
    project = entity(identity, "project", "Orchid Demo")
    memory = db.add(
        Entry(
            key="project.role", content="Alex works on Orchid", entity_id=alex["id"], confidence=0.8
        )
    )
    proposal = RelationshipInput(
        from_entity_id=alex["id"],
        to_entity_id=project["id"],
        predicate="works_on",
        evidence_id=memory["id"],
    )
    with pytest.raises(MemoryConflict):
        identity.relate(proposal)
    db.confirm(memory["id"], [])
    edge = identity.relate(proposal)
    assert identity.neighbours(alex["id"])["relationships"] == []
    identity.confirm(edge["id"], 1, relationship=True)
    assert identity.neighbours(alex["id"])["relationships"][0]["evidence_revision"] == 2
    assert identity.relate(proposal)["id"] == edge["id"]
    db.edit(memory["id"], Entry(key="project.role", content="Alex left Orchid"), 2)
    assert identity.neighbours(alex["id"])["relationships"] == []
    db.confirm(memory["id"], [])
    assert (
        identity.neighbours(alex["id"])["relationships"] == []
    )  # Old edge doesn't silently refresh.
    db.delete(memory["id"])
    assert not identity.relationships()
    assert not db.export()["relationship_revisions"]


def test_entity_edits_and_sensitive_identity_do_not_leak_linked_data(tmp_path):
    db = Store(str(tmp_path))
    identity = IdentityStore(db)
    alex = entity(identity, "person", "Alex Example", aliases=["Alex"])
    memory = db.add(Entry(key="role", content="SensitiveOrchid", entity_id=alex["id"]))
    db.confirm(memory["id"], [])
    changed = identity.edit(
        alex["id"], EntityInput(kind="person", name="Alex Example", sensitivity="sensitive"), 2
    )
    assert not db.context("SensitiveOrchid")
    identity.confirm(alex["id"], changed["revision"])
    assert identity.resolve("Alex")["status"] == "unknown"
    assert identity.resolve("Alex", allow_sensitive=True)["status"] == "resolved"
    assert not db.context("SensitiveOrchid")
    assert db.context("SensitiveOrchid", allow_sensitive=True)
    again = identity.edit(alex["id"], EntityInput(kind="person", name="Renamed Example"), 4)
    assert again["sensitivity"] == "sensitive" and again["aliases"] == ["Alex"]


def test_entity_forgetting_purges_linked_chains_sources_aliases_and_relations(tmp_path):
    db = Store(str(tmp_path))
    identity, learning = IdentityStore(db), LearningPipeline(db)
    person = entity(identity, "person", "Forgotten Example", aliases=["Forgotten alias"])
    other = entity(identity, "person", "Other Example")
    source = learning.register(
        SourceInput(kind="document", name="Forgotten Example notes", entity_id=person["id"])
    )
    learning.approve(source["id"])
    run = learning.ingest(
        source["id"], IngestionInput(content="fact private.role: ForgottenOrchid")
    )
    item_id = run["items"][0]["memory_id"]
    db.edit(item_id, Entry(key="private.role", content="OtherCedar", entity_id=other["id"]), 1)
    identity.delete(person["id"])
    exported = db.export()
    assert not exported["entries"] and not exported["revisions"] and not exported["origins"]
    assert not exported["sources"] and not exported["ingestion_runs"]
    assert "Forgotten" not in json.dumps(exported)
    assert identity.resolve("Forgotten alias")["status"] == "unknown"
    assert identity.entities()[0]["id"] == other["id"]


def test_validity_windows_preserve_nonoverlapping_history_and_exclude_future(tmp_path):
    db = Store(str(tmp_path))
    old = db.add(
        Entry(
            key="project",
            content="OldOrchid",
            valid_from="2020-01-01T00:00:00Z",
            valid_until="2021-01-01T00:00:00Z",
        )
    )
    current = db.add(Entry(key="project", content="NewCedar", valid_from="2021-01-01T00:00:00Z"))
    db.confirm(old["id"], [])
    db.confirm(current["id"], [])
    assert not db.context("OldOrchid")
    assert db.context("OldOrchid", as_of="2020-06-01T00:00:00Z")
    assert not db.context("NewCedar", as_of="2020-06-01T00:00:00Z")
    future = db.add(
        Entry(
            key="future", content="FutureMaple", valid_from=datetime.now(UTC) + timedelta(days=365)
        )
    )
    db.confirm(future["id"], [])
    assert not db.context("FutureMaple")
    at = datetime.now(UTC) + timedelta(days=366)
    assert db.context("FutureMaple", as_of=at)
    overlap = db.add(
        Entry(
            key="project",
            content="OverlappingElm",
            valid_from="2020-06-01T00:00:00Z",
            valid_until="2022-01-01T00:00:00Z",
        )
    )
    with pytest.raises(MemoryConflict) as error:
        db.confirm(overlap["id"], [])
    assert set(error.value.conflicts) == {old["id"], current["id"]}


def test_distinct_episodes_do_not_conflict_and_have_stable_time_identity(tmp_path):
    db = Store(str(tmp_path))
    learning = LearningPipeline(db)
    source = learning.register(SourceInput(kind="event", name="Synthetic episodes"))
    learning.approve(source["id"])
    first = learning.ingest(
        source["id"],
        IngestionInput(content="event demo: Completed a demo", occurred_at="2020-01-01T00:00:00Z"),
    )
    second = learning.ingest(
        source["id"],
        IngestionInput(content="event demo: Completed a demo", occurred_at="2020-02-01T00:00:00Z"),
    )
    assert first["items"][0]["memory_id"] != second["items"][0]["memory_id"]
    for run in (first, second):
        db.confirm(run["items"][0]["memory_id"], [])
    assert len(db.select(TemporalQuery())) == 2
    assert all(item["category"] == "episodic" for item in db.entries())
    alternate_zone = learning.ingest(
        source["id"],
        IngestionInput(
            content="event demo: Completed a demo", occurred_at="2019-12-31T19:00:00-05:00"
        ),
    )
    assert alternate_zone["id"] == first["id"] and alternate_zone["replayed"]


def test_knowledge_time_is_distinct_from_valid_time_and_cannot_revive_deleted_memory(tmp_path):
    db = Store(str(tmp_path))
    item = db.add(Entry(key="project", content="OldOrchid", valid_from="2020-01-01T00:00:00Z"))
    db.confirm(item["id"], [])
    past = datetime.now(UTC)
    assert not db.context(
        "OldOrchid", as_of="2020-06-01T00:00:00Z", known_at="2020-06-01T00:00:00Z"
    )
    assert db.context("OldOrchid", as_of="2020-06-01T00:00:00Z")  # Owner learned it later.
    db.edit(item["id"], Entry(key="project", content="NewCedar", sensitivity="sensitive"), 2)
    assert not db.context("OldOrchid", known_at=past)
    assert db.context("OldOrchid", known_at=past, allow_sensitive=True)
    db.delete(item["id"])
    assert not db.context("OldOrchid", known_at=past, allow_sensitive=True)


@pytest.mark.parametrize("belief", ["inferred", "disputed", "outdated", "unknown"])
def test_uncertain_beliefs_are_inspectable_but_not_current_facts(tmp_path, belief):
    db = Store(str(tmp_path))
    item = db.add(Entry(key="project", content="UncertainOrchid", belief=belief, confidence=0.4))
    db.confirm(item["id"], [])
    assert not db.context("UncertainOrchid")
    selected = db.select(TemporalQuery(include_uncertain=True))[0]
    assert selected["effective_belief"] == belief and selected["record"]["confidence"] == 0.4
    db.edit(item["id"], Entry(key="project", content="CorrectedCedar"), 2)
    assert db.entries()[0]["belief"] == belief and db.entries()[0]["confidence"] == 0.4


@pytest.mark.parametrize(
    "extra",
    [
        {"confidence": True},
        {"confidence": 1.1},
        {"confidence": float("nan")},
        {"confidence": "0.5"},
        {"valid_from": "2020-01-01"},
        {"occurred_at": "2020-01-01T00:00:00Z"},
        {"valid_from": "2021-01-01T00:00:00Z", "valid_until": "2020-01-01T00:00:00Z"},
    ],
)
def test_metadata_contract_rejects_unproven_or_malformed_values(extra):
    with pytest.raises(ValidationError):
        Entry(key="project", content="Synthetic", **extra)


def test_current_subject_privacy_floor_also_protects_historical_rebound_memory(tmp_path):
    db = Store(str(tmp_path))
    identity = IdentityStore(db)
    one = entity(identity, "person", "One Example")
    two = entity(identity, "person", "Two Example")
    item = db.add(Entry(key="role", content="HistoricalOrchid", entity_id=one["id"]))
    db.confirm(item["id"], [])
    past = datetime.now(UTC)
    db.edit(item["id"], Entry(key="role", content="CurrentCedar", entity_id=two["id"]), 2)
    changed = identity.edit(
        two["id"], EntityInput(kind="person", name="Two Example", sensitivity="sensitive"), 2
    )
    identity.confirm(two["id"], changed["revision"])
    assert not db.context("HistoricalOrchid", known_at=past)
    assert db.context("HistoricalOrchid", known_at=past, allow_sensitive=True)


def test_version_three_upgrade_preserves_sources_and_history_without_inventing_confidence(tmp_path):
    import sqlite3

    timestamp = "2020-01-01T00:00:00+00:00"
    with sqlite3.connect(tmp_path / "twin.sqlite3") as connection:
        connection.execute(
            "CREATE TABLE entries (id TEXT PRIMARY KEY,kind TEXT,key TEXT,content TEXT,"
            "source TEXT,status TEXT,created_at TEXT,updated_at TEXT,revision INTEGER,"
            "superseded_by TEXT,sensitivity TEXT)"
        )
        connection.execute(
            "INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy",
                "fact",
                "project",
                "LegacyOrchid",
                "manual",
                "confirmed",
                timestamp,
                timestamp,
                2,
                None,
                "private",
            ),
        )
        connection.execute(
            "CREATE TABLE revisions (id TEXT,kind TEXT,key TEXT,content TEXT,source TEXT,"
            "status TEXT,created_at TEXT,updated_at TEXT,revision INTEGER,superseded_by TEXT,"
            "change TEXT,sensitivity TEXT)"
        )
        connection.execute(
            "INSERT INTO revisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy",
                "fact",
                "project",
                "LegacyOrchid",
                "manual",
                "confirmed",
                timestamp,
                timestamp,
                2,
                None,
                "confirmed",
                "private",
            ),
        )
        connection.execute(
            "CREATE TABLE sources (id TEXT PRIMARY KEY,kind TEXT,name TEXT,sensitivity TEXT,"
            "approved INTEGER,revision INTEGER,created_at TEXT,updated_at TEXT)"
        )
        connection.execute(
            "INSERT INTO sources VALUES ('legacy-source','document','Synthetic','private',1,2,?,?)",
            (timestamp, timestamp),
        )
        connection.execute("PRAGMA user_version=3")
    db = Store(str(tmp_path))
    migrated = db.entries()[0]
    assert migrated["confidence"] is None and migrated["owner_id"] == db.owner_id
    assert migrated["entity_id"] is None and migrated["valid_until"] is None
    assert db.revisions("legacy")[0]["content"] == "LegacyOrchid"
    assert db.revisions("legacy")[0]["revision"] == 2
    assert db.export()["sources"][0]["owner_id"] == db.owner_id
    assert db.context("LegacyOrchid")
    assert MemoryExport.model_validate(db.export()).version == 5
