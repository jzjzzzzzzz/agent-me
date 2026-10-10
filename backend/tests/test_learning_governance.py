import json
from datetime import UTC, datetime, timedelta

import pytest

from app.agency import Agency
from app.agency_models import PermissionInput, ToolInvocation
from app.governance import LearningGovernance, RetentionApproval
from app.identity import IdentityStore
from app.learning_policy import LearningPolicyManager
from app.memory import MemoryConflict, Store
from app.memory_models import EntityInput, Entry, LearningPolicy, RelationshipInput, RetentionPolicy
from app.owner_control import OwnerControl
from app.owner_models import WorkspacePurge
from app.retention import RetentionManager


def old_record(db, *, confirmed=False):
    record = db.add(
        Entry(
            key="project.current",
            content="Fictional old record body",
            valid_until=datetime.now(UTC) - timedelta(days=4) if confirmed else None,
        )
    )
    if confirmed:
        db.confirm(record["id"], [], 1)
    old = (datetime.now(UTC) - timedelta(days=4)).isoformat()
    with db.connect() as connection:
        connection.execute("UPDATE entries SET updated_at=? WHERE id=?", (old, record["id"]))
    return next(row for row in db.entries() if row["id"] == record["id"])


def approval(review):
    return RetentionApproval(digest=review.digest, scope_digest=review.scope_digest)


def test_governance_state_is_single_owner_and_retention_review_has_no_committed_effect(tmp_path):
    db = Store(tmp_path)
    item = old_record(db)
    retention = RetentionManager(db)
    retention.configure(RetentionPolicy(pending_days=1), 1, expected_owner_id=db.owner_id)
    plan = retention.preview(expected_owner_id=db.owner_id)
    manager = LearningGovernance(db)
    before = db.export()
    state = manager.state()
    assert state.owner_id == db.owner_id and state.retention.policy.pending_days == 1
    review = manager.review_retention(plan["id"])
    assert db.export() == before and review.removed_counts["entries"] == 1
    assert review.removed_counts["revisions"] == 1 and review.forgetting_counts["added"] == 1
    assert "Fictional old record body" not in review.model_dump_json()
    assert manager.review_retention(plan["id"]).scope_digest == review.scope_digest
    result = manager.apply_retention(plan["id"], approval(review))
    assert result["status"] == "applied" and not db.entries()
    assert manager.apply_retention(plan["id"], approval(review)) == result
    assert not any(row["id"] == item["id"] for row in db.export()["revisions"])


def test_new_relationship_with_unchanged_memory_revision_invalidates_retention_copy_scope(tmp_path):
    db = Store(tmp_path)
    item = old_record(db, confirmed=True)
    retention = RetentionManager(db)
    retention.configure(RetentionPolicy(expired_days=1), 1)
    plan = retention.preview()
    manager = LearningGovernance(db)
    review = manager.review_retention(plan["id"])
    identity = IdentityStore(db)
    entities = []
    for kind in ("person", "project"):
        row = identity.add(EntityInput(kind=kind, name=f"Fictional {kind}"))
        entities.append(identity.confirm(row["id"], 1))
    relation = identity.relate(
        RelationshipInput(
            from_entity_id=entities[0]["id"],
            to_entity_id=entities[1]["id"],
            evidence_id=item["id"],
            predicate="works_on",
        )
    )
    before = db.export()
    with pytest.raises(MemoryConflict, match="copy scope changed"):
        manager.apply_retention(plan["id"], approval(review))
    assert db.export() == before
    fresh = manager.review_retention(plan["id"])
    assert fresh.removed_counts["relationships"] == 1
    manager.apply_retention(plan["id"], approval(fresh))
    assert not identity.relationships()
    assert relation["id"]


def test_retention_policy_or_target_changes_block_the_review_and_independent_copies_are_kept(
    tmp_path,
):
    db = Store(tmp_path)
    item = old_record(db, confirmed=True)
    agency = Agency(db)
    agency.configure("notes.create", PermissionInput(enabled=True), 1)
    # Create the copy while evidence is current, then expire that reviewed revision.
    with db.connect() as connection:
        connection.execute("UPDATE entries SET valid_until=NULL WHERE id=?", (item["id"],))
    note = agency.plan(
        ToolInvocation(
            tool="notes.create",
            arguments={"title": "Fictional retained note", "content": "Fictional independent body"},
            source_ids=[item["id"]],
            idempotency_key="retained-copy",
        )
    )
    agency.approve(note["id"], 1, note["digest"])
    agency.execute(note["id"])
    with db.connect() as connection:
        connection.execute(
            "UPDATE entries SET valid_until=? WHERE id=?",
            ((datetime.now(UTC) - timedelta(days=4)).isoformat(), item["id"]),
        )
    retention = RetentionManager(db)
    retention.configure(RetentionPolicy(expired_days=1), 1)
    plan = retention.preview()
    manager = LearningGovernance(db)
    review = manager.review_retention(plan["id"])
    assert review.retained_counts == {"notes": 1, "action_plans": 1, "action_events": 4}
    retention.configure(RetentionPolicy(expired_days=2), 2)
    with pytest.raises(MemoryConflict, match="policy changed"):
        manager.apply_retention(plan["id"], approval(review))
    fresh_plan = retention.preview()
    fresh = manager.review_retention(fresh_plan["id"])
    manager.apply_retention(fresh_plan["id"], approval(fresh))
    assert not db.entries() and len(agency.notes()) == 1 and len(agency.plans()) == 1


def test_retention_plan_digest_rejects_changed_target_set_and_real_apply_failure_rolls_back(
    tmp_path, monkeypatch
):
    db = Store(tmp_path)
    old_record(db)
    retention = RetentionManager(db)
    retention.configure(RetentionPolicy(pending_days=1), 1)
    plan = retention.preview()
    manager = LearningGovernance(db)
    review = manager.review_retention(plan["id"])
    with db.connect() as connection:
        changed = {**plan, "targets": []}
        connection.execute(
            "UPDATE retention_plans SET data_json=? WHERE id=?", (json.dumps(changed), plan["id"])
        )
    with pytest.raises(MemoryConflict, match="exact reviewed plan"):
        manager.apply_retention(plan["id"], approval(review))
    with db.connect() as connection:
        connection.execute(
            "UPDATE retention_plans SET data_json=? WHERE id=?", (json.dumps(plan), plan["id"])
        )
    before = db.export()
    real = manager.retention._apply
    calls = 0

    def fail(*args):
        nonlocal calls
        calls += 1
        result = real(*args)
        if calls == 2:
            raise RuntimeError("Fictional post-write failure")
        return result

    monkeypatch.setattr(manager.retention, "_apply", fail)
    with pytest.raises(RuntimeError):
        manager.apply_retention(plan["id"], approval(review))
    assert db.export() == before


def test_policy_and_preview_owner_preconditions_reject_reset_revision_after_purge(tmp_path):
    from app.consolidation import ConsolidationManager

    db = Store(tmp_path)
    owner = db.owner_id
    OwnerControl(db).purge(
        WorkspacePurge(expected_owner_id=owner, confirmation="erase-personal-workspace")
    )
    before = db.export()
    for call in [
        lambda: LearningPolicyManager(db).configure(
            LearningPolicy(max_candidates=1), 1, expected_owner_id=owner
        ),
        lambda: RetentionManager(db).configure(
            RetentionPolicy(pending_days=1), 1, expected_owner_id=owner
        ),
        lambda: RetentionManager(db).preview(expected_owner_id=owner),
        lambda: ConsolidationManager(db).preview(expected_owner_id=owner),
    ]:
        with pytest.raises(MemoryConflict):
            call()
        assert db.export() == before


def test_oldest_as_of_does_not_overflow_and_future_retention_cannot_execute(tmp_path):
    db = Store(tmp_path)
    old_record(db)
    retention = RetentionManager(db)
    retention.configure(RetentionPolicy(pending_days=365000), 1)
    earliest = retention.preview(as_of=datetime.min.replace(tzinfo=UTC))
    assert earliest["targets"] == []
    future = retention.preview(as_of=datetime.now(UTC) + timedelta(days=365001))
    with pytest.raises(MemoryConflict, match="Future retention"):
        LearningGovernance(db).review_retention(future["id"])


async def test_private_governance_api_exposes_scope_and_applies_exact_two_digests(personal):
    client, config = personal
    db = Store(config.personal_data_dir)
    old_record(db)
    headers = {"Authorization": f"Bearer {config.personal_token}"}
    assert (await client.get("/api/v1/personal/learning/governance")).status_code == 401
    state = await client.get("/api/v1/personal/learning/governance", headers=headers)
    assert state.headers["cache-control"] == "no-store"
    owner = state.json()["owner_id"]
    assert (
        await client.post(
            "/api/v1/personal/retention/policy",
            headers=headers,
            json={
                "policy": {"pending_days": 1},
                "expected_revision": 1,
                "expected_owner_id": owner,
            },
        )
    ).status_code == 200
    plan = (
        await client.post(
            "/api/v1/personal/retention/preview", headers=headers, json={"expected_owner_id": owner}
        )
    ).json()
    review = (
        await client.get(f"/api/v1/personal/retention/plans/{plan['id']}/review", headers=headers)
    ).json()
    assert "Fictional old record body" not in json.dumps(review)
    wrong = await client.post(
        f"/api/v1/personal/retention/plans/{plan['id']}/apply-reviewed",
        headers=headers,
        json={"digest": review["digest"], "scope_digest": "0" * 64},
    )
    assert wrong.status_code == 409 and db.entries()
    result = await client.post(
        f"/api/v1/personal/retention/plans/{plan['id']}/apply-reviewed",
        headers=headers,
        json={"digest": review["digest"], "scope_digest": review["scope_digest"]},
    )
    assert result.status_code == 200 and not db.entries()


def test_governance_cli_requires_exact_digests_and_explicit_execution(tmp_path, capsys):
    from app.agent_cli import main

    root = tmp_path / "cli"
    db = Store(root)
    old_record(db)
    RetentionManager(db).configure(RetentionPolicy(pending_days=1), 1)
    plan = RetentionManager(db).preview()

    def cli(*args):
        status = main(["--data-dir", str(root), *args])
        output = capsys.readouterr()
        return status, json.loads(output.err if status == 2 else output.out)

    assert cli("governance", "state")[1]["owner_id"] == db.owner_id
    status, reviewed = cli("governance", "retention-review", plan["id"])
    assert status == 0 and db.entries()
    arguments = [
        "governance",
        "retention-apply",
        plan["id"],
        "--digest",
        reviewed["digest"],
        "--scope-digest",
        reviewed["scope_digest"],
    ]
    assert cli(*arguments)[0] == 2 and db.entries()
    assert cli(*arguments, "--yes")[1]["status"] == "applied" and not db.entries()
    assert cli(*arguments, "--yes")[1]["status"] == "applied"
    assert (
        cli(
            "learning",
            "configure",
            "--expected-revision",
            "1",
            "--expected-owner-id",
            "fictional-other-owner",
            "--policy-json",
            "{}",
        )[0]
        == 2
    )
