"""Explicit owner erasure of independent source/action/output/archive data copies."""

import json
from collections import defaultdict
from uuid import uuid4

from .audit import record
from .identity_schema import records
from .memory import MemoryConflict, MemoryInputError, MemoryNotFound, Store
from .owner_models import WorkspacePurge
from .portability import DATA_TABLES


class OwnerControl:
    def __init__(self, store: Store):
        self.store = store

    @staticmethod
    def _owner(db):
        return db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]

    def _object(self, db, table, item_id, revision):
        row = db.execute(f"SELECT data_json FROM {table} WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise MemoryNotFound("Owner data copy not found")
        item = json.loads(row[0])
        if (
            item["owner_id"] != self._owner(db)
            or type(revision) is not int
            or item["revision"] != revision
        ):
            raise MemoryConflict("Owner data copy changed; review its current revision")
        return item

    @staticmethod
    def _erase_plan(db, item_id):
        db.execute(
            "DELETE FROM action_events WHERE json_extract(data_json,'$.plan_id')=?", (item_id,)
        )
        db.execute("DELETE FROM action_plans WHERE id=?", (item_id,))

    @classmethod
    def _erase_output(cls, db, table, item_id, created_by):
        for plan in records(db, "action_plans"):
            result = plan.get("result") or {}
            if (
                plan["id"] == created_by
                or result.get("table") == table
                and result.get("id") == item_id
                or table == "tasks"
                and plan["invocation"]["arguments"].get("task_id") == item_id
            ):
                cls._erase_plan(db, plan["id"])
        db.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))

    def delete_output(self, table, item_id, expected_revision):
        if table not in {"tasks", "notes"}:
            raise MemoryInputError("Only task/note outputs can be erased")
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = self._object(db, table, item_id, expected_revision)
            self._erase_output(db, table, item_id, item["created_by"])
            record(db, "owner.output_delete", counts={"deleted": 1})
        return {"deleted": True}

    def delete_action(
        self, item_id, expected_revision, *, purge_output=False, expected_output_revision=None
    ):
        if type(purge_output) is not bool:
            raise MemoryInputError("Output erasure must be an explicit boolean")
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            plan = self._object(db, "action_plans", item_id, expected_revision)
            if purge_output:
                result = plan.get("result")
                if not result or not result.get("id"):
                    raise MemoryConflict("Action has no existing output to erase")
                table = "notes" if plan["invocation"]["tool"] == "notes.create" else "tasks"
                target = self._object(db, table, result["id"], expected_output_revision)
                self._erase_output(db, table, target["id"], target["created_by"])
            self._erase_plan(db, item_id)
            record(db, "owner.action_delete", counts={"deleted": 1, "outputs": int(purge_output)})
        return {"deleted": True}

    def delete_source(self, source_id, expected_revision, *, forget_memories=False):
        if type(forget_memories) is not bool:
            raise MemoryInputError("Derived memory erasure must be an explicit boolean")
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            source = db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
            if not source:
                raise MemoryNotFound("Learning source not found")
            if (
                source["owner_id"] != self._owner(db)
                or type(expected_revision) is not int
                or source["revision"] != expected_revision
            ):
                raise MemoryConflict("Learning source changed; review its current revision")
            targets = {
                row[0]
                for row in db.execute(
                    "SELECT memory_id FROM origins WHERE source_id=?", (source_id,)
                )
            }
            targets.update(
                row[0]
                for row in db.execute(
                    "SELECT id FROM revisions WHERE source=?", (f"source:{source_id}",)
                )
            )
            if forget_memories:
                # Include explicitly restored descendants; no free-text/semantic erasure guessing.
                descendants = defaultdict(set)
                for row in db.execute("SELECT id,source FROM revisions"):
                    if row["source"].startswith("memory:"):
                        parent, _, revision = row["source"][7:].rpartition("@")
                        if revision.isdecimal():
                            descendants[parent].add(row["id"])
                queue = list(targets)
                while queue:
                    for item_id in descendants[queue.pop()]:
                        if item_id not in targets:
                            targets.add(item_id)
                            queue.append(item_id)
                for item_id in targets:
                    self.store._delete(db, item_id)
            db.execute("DELETE FROM origins WHERE source_id=?", (source_id,))
            db.execute(
                "DELETE FROM ingestion_runs WHERE json_extract(run_json,'$.source_id')=?",
                (source_id,),
            )
            db.execute("DELETE FROM sources WHERE id=?", (source_id,))
            record(
                db,
                "owner.source_delete",
                counts={"sources": 1, "memories": len(targets) if forget_memories else 0},
            )
        return {"deleted": True, "forgotten_memories": len(targets) if forget_memories else 0}

    def archives(self):
        with self.store.connect() as db:
            return records(db, "import_archives")[-100:]

    def delete_archive(self, archive_id):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT data_json FROM import_archives WHERE id=?", (archive_id,)
            ).fetchone()
            if not row or json.loads(row[0])["owner_id"] != self._owner(db):
                raise MemoryNotFound("Import archive not found")
            db.execute("DELETE FROM import_archives WHERE id=?", (archive_id,))
            record(db, "owner.archive_delete", counts={"deleted": 1})
        return {"deleted": True}

    def purge(self, review: WorkspacePurge):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if review.expected_owner_id != self._owner(db):
                raise MemoryConflict("Workspace owner changed; review before erasing")
            counts = {}
            for table in (*DATA_TABLES, "audit_events", "memory_digests"):
                counts[table] = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                db.execute(f"DELETE FROM {table}")
            db.execute("DELETE FROM workspace")
            new_owner = uuid4().hex
            db.executemany(
                "INSERT INTO workspace VALUES (?,?)",
                [
                    ("owner_id", new_owner),
                    ("retention_policy", "{}"),
                    ("retention_revision", "1"),
                    ("learning_policy", "{}"),
                    ("learning_revision", "1"),
                    ("disclosure_policy", "{}"),
                    ("disclosure_revision", "1"),
                ],
            )
            record(db, "owner.workspace_purge", counts={"deleted": sum(counts.values())})
        return {"scope": "sqlite_state", "deleted_counts": counts, "owner_id": new_owner}
