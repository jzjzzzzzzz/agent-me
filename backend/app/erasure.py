"""Exact selective erasure scope from the real mutation rolled back to a SQLite savepoint."""

import hashlib
import json
from collections import Counter

from .erasure_models import (
    ErasureApproval,
    ErasureCatalogue,
    ErasureChoice,
    ErasurePreview,
    ErasureRef,
    ErasureRequest,
    ErasureResult,
)
from .memory import MemoryConflict, MemoryNotFound, record_digest
from .owner_control import OwnerControl

TABLES = (
    "tasks",
    "notes",
    "action_plans",
    "action_events",
    "entries",
    "revisions",
    "sources",
    "ingestion_runs",
    "origins",
    "relationships",
    "relationships_revisions",
    "memory_digests",
    "forgotten",
    "import_archives",
)
TARGETS = {
    "task": "tasks",
    "note": "notes",
    "action": "action_plans",
    "source": "sources",
    "archive": "import_archives",
}


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")


def fingerprint(value):
    return hashlib.sha256(encode(value)).hexdigest()


def content(row):
    return (
        json.loads(row["data_json"])
        if "data_json" in row
        else json.loads(row["run_json"])
        if "run_json" in row
        else row
    )


def snapshot(db, *, tables=TABLES):
    result = {}
    for table in tables:
        columns = sorted(
            (row for row in db.execute(f"PRAGMA table_info({table})") if row["pk"]),
            key=lambda row: row["pk"],
        )
        names = [row["name"] for row in columns]
        result[table] = {
            fingerprint([row[name] for name in names]): dict(row)
            for row in db.execute(f"SELECT * FROM {table}")
        }
    return result


def reference(table, key, row):
    value = content(row)
    return ErasureRef(
        table=table,
        key=key,
        id=value.get("id") or value.get("memory_id") or value.get("digest") or key,
        revision=value.get("revision"),
        label=value.get("title")
        or value.get("name")
        or value.get("key")
        or value.get("predicate")
        or value.get("invocation", {}).get("tool")
        or table,
    )


class ReviewedErasure:
    def __init__(self, store):
        self.store = store
        self.owner = OwnerControl(store)

    def catalogue(self):
        with self.store.connect() as db:
            db.execute("BEGIN")
            owner_id = self.owner._owner(db)
            items = []
            for kind, table in TARGETS.items():
                query = f"SELECT * FROM {table} ORDER BY rowid"
                if kind in {"action", "archive"}:
                    query = f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 100"
                for raw in db.execute(query):
                    row = dict(raw)
                    value = content(row)
                    if value["owner_id"] != owner_id:
                        raise MemoryConflict("Erasure catalogue contains another workspace owner")
                    items.append(
                        ErasureChoice(
                            kind=kind, record=reference(table, fingerprint([value["id"]]), row)
                        )
                    )
            return ErasureCatalogue(owner_id=owner_id, items=items)

    def _request(self, db, request):
        if request.expected_owner_id != self.owner._owner(db):
            raise MemoryConflict("Workspace owner changed; review erasure again")
        if (
            request.kind == "action"
            and request.purge_output
            and request.expected_output_revision is None
        ):
            plan = self.owner._object(db, "action_plans", request.id, request.expected_revision)
            result = plan.get("result") or {}
            table = "notes" if plan["invocation"]["tool"] == "notes.create" else "tasks"
            row = db.execute(
                f"SELECT data_json FROM {table} WHERE id=?", (result.get("id"),)
            ).fetchone()
            if not row:
                raise MemoryNotFound("Action output is not available for erasure")
            request = request.model_copy(
                update={"expected_output_revision": json.loads(row[0])["revision"]}
            )
        return request

    def _apply(self, db, request):
        if request.kind in {"task", "note"}:
            return self.owner._delete_output(
                db, TARGETS[request.kind], request.id, request.expected_revision
            )
        if request.kind == "action":
            return self.owner._delete_action(
                db,
                request.id,
                request.expected_revision,
                purge_output=request.purge_output,
                expected_output_revision=request.expected_output_revision,
            )
        if request.kind == "source":
            return self.owner._delete_source(
                db, request.id, request.expected_revision, forget_memories=request.forget_memories
            )
        return self.owner._delete_archive(db, request.id)

    def _retained(self, before, request, memory_ids):
        selected = []
        linked_plans = {
            content(row)["id"]
            for row in before["action_plans"].values()
            if memory_ids.intersection(content(row)["invocation"].get("source_ids", []))
        }
        linked_sources = {
            content(row)["source_id"]
            for row in before["origins"].values()
            if content(row)["memory_id"] in memory_ids
        }
        linked_sources.update(
            content(row)["source_id"]
            for row in before["ingestion_runs"].values()
            if any(item.get("memory_id") in memory_ids for item in content(row).get("items", []))
        )
        plans = (
            [
                content(row)
                for row in before["action_plans"].values()
                if content(row)["id"] == request.id
            ]
            if request.kind == "action"
            else []
        )
        output = (plans[0].get("result") or {}) if plans else {}
        for table in TABLES:
            for key, row in before[table].items():
                value = content(row)
                linked = False
                if request.kind == "action" and table in {"tasks", "notes"}:
                    linked = (
                        value.get("created_by") == request.id
                        or output.get("table") == table
                        and output.get("id") == value.get("id")
                    )
                if request.kind == "source":
                    if table in {"entries", "revisions"}:
                        linked = value.get("id") in memory_ids
                    elif table in {"origins", "memory_digests"}:
                        linked = value.get("memory_id") in memory_ids
                    elif table in {"relationships", "relationships_revisions"}:
                        linked = value.get("evidence_id") in memory_ids
                    elif table in {"tasks", "notes", "action_plans"}:
                        call = value.get("invocation", value)
                        linked = bool(memory_ids.intersection(call.get("source_ids", [])))
                    elif table == "action_events":
                        linked = value.get("plan_id") in linked_plans
                    elif table == "ingestion_runs":
                        linked = any(
                            item.get("memory_id") in memory_ids for item in value.get("items", [])
                        )
                    elif table == "sources":
                        linked = value.get("id") in linked_sources
                if linked:
                    selected.append((table, key, row))
        return selected

    def _scope(self, db, request):
        request = self._request(db, request)
        before = snapshot(db)
        target_table = TARGETS[request.kind]
        target = next(
            (
                (key, row)
                for key, row in before[target_table].items()
                if content(row).get("id") == request.id
            ),
            None,
        )
        if not target:
            raise MemoryNotFound("Erasure target not found")
        memories = (
            self.owner._source_targets(db, request.id, descendants=True)
            if request.kind == "source"
            else set()
        )
        linked = self._retained(before, request, memories)
        refreshed_hashes = {
            fingerprint([record_digest(row)])
            for row in before["revisions"].values()
            if request.kind == "source" and request.forget_memories and row["id"] in memories
        }
        db.execute("SAVEPOINT owner_erasure_preview")
        try:
            self._apply(db, request)
            after = snapshot(db)
        finally:
            db.execute("ROLLBACK TO owner_erasure_preview")
            db.execute("RELEASE owner_erasure_preview")
        removed, updated, added, retained, bindings = [], [], [], [], []
        for table in TABLES:
            for key, row in before[table].items():
                if key not in after[table]:
                    removed.append(reference(table, key, row))
                    bindings.append(["removed", table, key, row])
                elif row != after[table][key] or table == "forgotten" and key in refreshed_hashes:
                    updated.append(reference(table, key, row))
                    bindings.append(["updated", table, key, row])
            for key, row in after[table].items():
                if key not in before[table]:
                    added.append(reference(table, key, row))
                    # Hash keys are deterministic; generated timestamps are not authority.
                    bindings.append(["added", table, key])
        for table, key, row in linked:
            if key in after[table] and row == after[table][key]:
                retained.append(reference(table, key, row))
                bindings.append(["retained", table, key, row])
        bindings.sort(key=lambda item: (item[0], item[1], item[2]))

        def ordered(items):
            return sorted(
                items, key=lambda item: (item.table, item.id, item.revision or 0, item.key)
            )

        return ErasurePreview(
            request=request,
            target=reference(target_table, *target),
            digest=fingerprint([request.model_dump(mode="json"), bindings]),
            removed=ordered(removed),
            updated=ordered(updated),
            added=ordered(added),
            retained=ordered(retained),
        )

    def preview(self, request: ErasureRequest):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._scope(db, request)

    def apply(self, approval: ErasureApproval):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            scope = self._scope(db, approval.request)
            if scope.digest != approval.digest or scope.request != approval.request:
                raise MemoryConflict("Erasure scope changed; preview and review it again")
            result = self._apply(db, scope.request)
            return ErasureResult(
                request=scope.request,
                digest=scope.digest,
                removed_counts=dict(Counter(item.table for item in scope.removed)),
                retained_counts=dict(Counter(item.table for item in scope.retained)),
                forgotten_memories=result.get("forgotten_memories", 0),
            )
