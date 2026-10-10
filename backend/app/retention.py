"""Opt-in forgetting policy with reviewable, stale-safe, atomic execution plans."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from .memory import MemoryConflict, MemoryInputError, MemoryNotFound, Store
from .memory_models import RetentionPlan, RetentionPolicy
from .memory_time import utc


def fingerprint(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def old_enough(base, at, days):
    try:
        cutoff = at - timedelta(days=days)
    except OverflowError:
        return False  # No representable stored time predates the mathematical cutoff.
    return base <= cutoff


class RetentionManager:
    def __init__(self, store: Store):
        self.store = store

    @staticmethod
    def _settings(db):
        revision = db.execute(
            "SELECT value FROM workspace WHERE key='retention_revision'"
        ).fetchone()[0]
        policy = db.execute("SELECT value FROM workspace WHERE key='retention_policy'").fetchone()[
            0
        ]
        return {"revision": int(revision), "policy": json.loads(policy)}

    def settings(self):
        with self.store.connect() as db:
            db.execute("BEGIN")
            return self._settings(db)

    def configure(self, policy: RetentionPolicy, expected_revision: int, *, expected_owner_id=None):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            settings = self._settings(db)
            owner = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
            if expected_owner_id is not None and expected_owner_id != owner:
                raise MemoryConflict("Retention policy owner changed; review it again")
            if type(expected_revision) is not int or expected_revision != settings["revision"]:
                raise MemoryConflict("Retention policy changed; review it again")
            db.execute(
                "UPDATE workspace SET value=? WHERE key='retention_policy'",
                (policy.model_dump_json(),),
            )
            db.execute(
                "UPDATE workspace SET value=? WHERE key='retention_revision'",
                (str(settings["revision"] + 1),),
            )
            return self._settings(db)

    def preview(self, *, as_of=None, expected_owner_id=None):
        at = utc(as_of) or datetime.now(UTC)
        targets = []
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            owner = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
            if expected_owner_id is not None and expected_owner_id != owner:
                raise MemoryConflict("Retention preview owner changed; review it again")
            settings = self._settings(db)
            policy = RetentionPolicy.model_validate(settings["policy"])
            for raw in db.execute("SELECT * FROM entries ORDER BY rowid"):
                item = dict(raw)
                days = (
                    policy.pending_days
                    if item["status"] == "pending"
                    else policy.superseded_days
                    if item["status"] == "superseded"
                    else None
                )
                base = utc(item["updated_at"])
                if item["status"] == "confirmed" and item["valid_until"] is not None:
                    days, base = policy.expired_days, utc(item["valid_until"])
                if days is not None and old_enough(base, at, days):
                    targets.append(
                        dict(
                            table="entries",
                            id=item["id"],
                            revision=item["revision"],
                            fingerprint=None,
                        )
                    )
            if policy.history_days is not None:
                for row in db.execute("SELECT * FROM turns ORDER BY rowid"):
                    if old_enough(utc(row["created_at"]), at, policy.history_days):
                        targets.append(
                            dict(
                                table="turns",
                                id=row["id"],
                                revision=None,
                                fingerprint=fingerprint(json.dumps(dict(row), sort_keys=True)),
                            )
                        )
            if policy.run_days is not None:
                for row in db.execute("SELECT * FROM ingestion_runs ORDER BY rowid"):
                    run = json.loads(row["run_json"])
                    if old_enough(utc(run["updated_at"]), at, policy.run_days):
                        targets.append(
                            dict(
                                table="ingestion_runs",
                                id=row["id"],
                                revision=None,
                                fingerprint=fingerprint(row["run_json"]),
                            )
                        )
            if len(targets) > 1000:
                raise MemoryInputError("Retention preview exceeds 1000 targets; narrow the policy")
            owner = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
            plan = RetentionPlan(
                id=uuid4().hex,
                owner_id=owner,
                status="planned",
                policy_revision=settings["revision"],
                as_of=at,
                created_at=datetime.now(UTC),
                targets=targets,
            ).model_dump(mode="json")
            db.execute("INSERT INTO retention_plans VALUES (?,?)", (plan["id"], json.dumps(plan)))
        return plan

    def plans(self):
        with self.store.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT data_json FROM retention_plans ORDER BY rowid DESC LIMIT 100"
                )
            ]

    def apply(self, plan_id: str):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._apply(db, plan_id)

    def _apply(self, db, plan_id: str):
        row = db.execute("SELECT data_json FROM retention_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            raise MemoryNotFound("Retention plan not found")
        plan = RetentionPlan.model_validate(json.loads(row[0])).model_dump(mode="json")
        if (
            plan["owner_id"]
            != db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
        ):
            raise MemoryConflict("Retention plan belongs to another workspace")
        if plan["status"] == "applied":
            return plan
        if utc(plan["as_of"]) > datetime.now(UTC):
            raise MemoryConflict(
                "Future retention preview cannot execute before its effective time"
            )
        if plan["policy_revision"] != self._settings(db)["revision"]:
            raise MemoryConflict("Retention policy changed; create a new preview")
        for target in plan["targets"]:
            table = target["table"]
            item = db.execute(f"SELECT * FROM {table} WHERE id=?", (target["id"],)).fetchone()
            if not item:
                raise MemoryConflict("Retention targets changed; create a new preview")
            actual = (
                item["revision"]
                if table == "entries"
                else fingerprint(
                    item["run_json"]
                    if table == "ingestion_runs"
                    else json.dumps(dict(item), sort_keys=True)
                )
            )
            if actual != (target["revision"] if table == "entries" else target["fingerprint"]):
                raise MemoryConflict("Retention targets changed; create a new preview")
        for target in plan["targets"]:
            table = target["table"]
            if table == "entries":
                self.store._delete(db, target["id"])
            else:
                db.execute(f"DELETE FROM {table} WHERE id=?", (target["id"],))
            plan["deleted_counts"][table] += 1
        plan["status"] = "applied"
        db.execute("UPDATE retention_plans SET data_json=? WHERE id=?", (json.dumps(plan), plan_id))
        return plan
