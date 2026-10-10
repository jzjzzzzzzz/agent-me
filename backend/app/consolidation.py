"""Reviewed exact cross-record consolidation; preserves history and source provenance."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from .identity_schema import records
from .memory import MemoryConflict, MemoryInputError, MemoryNotFound, Store
from .memory_models import ConsolidationFilter, ConsolidationPlan, Entry, MemoryRecord


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def signature(item):
    # Every literal value and epistemic/privacy/time qualifier must match. No semantic merge.
    return fingerprint({field: item[field] for field in Entry.model_fields})


def record_fingerprint(item):
    return fingerprint(MemoryRecord.model_validate(item).model_dump(mode="json"))


def plan_digest(plan):
    return fingerprint({key: plan[key] for key in ("id", "owner_id", "groups", "created_at")})


class ConsolidationManager:
    def __init__(self, store: Store):
        self.store = store

    def preview(self, selection: ConsolidationFilter | None = None, *, expected_owner_id=None):
        from .learning_policy import matches_prefix

        selection = selection or ConsolidationFilter()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            owner = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
            if expected_owner_id is not None and expected_owner_id != owner:
                raise MemoryConflict("Consolidation preview owner changed; review it again")
            groups = {}
            # Prefer an already confirmed keeper, then the earliest record.
            for raw in db.execute(
                "SELECT * FROM entries WHERE status!='superseded' AND owner_id=? "
                "ORDER BY (status='confirmed') DESC,rowid",
                (owner,),
            ):
                item = dict(raw)
                if selection.entity_id is not None and item["entity_id"] != selection.entity_id:
                    continue
                if selection.kinds is not None and item["kind"] not in selection.kinds:
                    continue
                if selection.key_prefix is not None and not matches_prefix(
                    item["key"], [selection.key_prefix]
                ):
                    continue
                groups.setdefault(signature(item), []).append(item)
            targets = []
            for members in groups.values():
                if len(members) < 2:
                    continue
                targets.append(
                    {
                        "keeper_id": members[0]["id"],
                        "members": [
                            {
                                "id": item["id"],
                                "revision": item["revision"],
                                "fingerprint": record_fingerprint(item),
                            }
                            for item in members
                        ],
                    }
                )
            if len(targets) > 100 or sum(len(group["members"]) for group in targets) > 1000:
                raise MemoryInputError("Consolidation exceeds 100 groups or 1000 records")
            plan = dict(
                id=uuid4().hex,
                owner_id=owner,
                groups=targets,
                status="planned",
                created_at=datetime.now(UTC).isoformat(),
                merged_count=0,
            )
            plan["digest"] = "0" * 64
            plan = ConsolidationPlan.model_validate(plan).model_dump(mode="json")
            plan["digest"] = plan_digest(plan)
            db.execute(
                "INSERT INTO consolidation_plans VALUES (?,?)", (plan["id"], json.dumps(plan))
            )
            return plan

    def plans(self):
        with self.store.connect() as db:
            return records(db, "consolidation_plans")[-100:]

    def apply(self, plan_id: str, reviewed_digest: str):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT data_json FROM consolidation_plans WHERE id=?", (plan_id,)
            ).fetchone()
            if not row:
                raise MemoryNotFound("Consolidation plan not found")
            plan = ConsolidationPlan.model_validate_json(row[0]).model_dump(mode="json")
            if plan["digest"] != reviewed_digest or plan_digest(plan) != plan["digest"]:
                raise MemoryConflict("Consolidation approval must match the reviewed preview")
            owner = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
            if plan["owner_id"] != owner:
                raise MemoryConflict("Consolidation plan belongs to another workspace")
            if plan["status"] == "applied":
                return plan
            seen = set()
            for group in plan["groups"]:
                signatures = set()
                for target in group["members"]:
                    current = db.execute(
                        "SELECT * FROM entries WHERE id=?", (target["id"],)
                    ).fetchone()
                    if not current or record_fingerprint(dict(current)) != target["fingerprint"]:
                        raise MemoryConflict("Consolidation targets changed; preview again")
                    if (
                        current["owner_id"] != owner
                        or current["status"] == "superseded"
                        or target["id"] in seen
                    ):
                        raise MemoryConflict("Invalid consolidation membership")
                    seen.add(target["id"])
                    signatures.add(signature(dict(current)))
                ids = [target["id"] for target in group["members"]]
                if group["keeper_id"] not in ids or len(signatures) != 1:
                    raise MemoryConflict("Invalid consolidation membership")
            now = datetime.now(UTC).isoformat()
            for group in plan["groups"]:
                keeper = group["keeper_id"]
                # Corroboration is a new revision; pending memory is still pending.
                db.execute(
                    "UPDATE entries SET revision=revision+1,updated_at=? WHERE id=?", (now, keeper)
                )
                keeper_revision = db.execute(
                    "SELECT revision FROM entries WHERE id=?", (keeper,)
                ).fetchone()[0]
                for target in group["members"]:
                    if target["id"] == keeper:
                        continue
                    for raw in db.execute(
                        "SELECT * FROM origins WHERE memory_id=?", (target["id"],)
                    ).fetchall():
                        origin = dict(raw)
                        origin.update(
                            id=uuid4().hex, memory_id=keeper, memory_revision=keeper_revision
                        )
                        columns = list(origin)
                        db.execute(
                            f"INSERT OR IGNORE INTO origins ({','.join(columns)}) "
                            f"VALUES ({','.join('?' for _ in columns)})",
                            [origin[key] for key in columns],
                        )
                    db.execute(
                        "UPDATE entries SET status='superseded',superseded_by=?,"
                        "revision=revision+1,updated_at=? WHERE id=?",
                        (keeper, now, target["id"]),
                    )
                    self.store._snapshot(db, target["id"], "superseded")
                    plan["merged_count"] += 1
                self.store._snapshot(db, keeper, "corroborated")
            plan["status"] = "applied"
            db.execute(
                "UPDATE consolidation_plans SET data_json=? WHERE id=?", (json.dumps(plan), plan_id)
            )
            return plan
