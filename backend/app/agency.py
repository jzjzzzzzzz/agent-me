"""Transactional local agency: explicit permissions, immutable plans, owner approval and undo."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from .agency_models import (
    NoteCreateArgs,
    PermissionInput,
    TaskCompleteArgs,
    TaskCreateArgs,
    ToolInvocation,
)
from .identity_schema import records
from .memory import MemoryConflict, MemoryInputError, MemoryNotFound, MemoryPermissionDenied, Store
from .memory_time import active_at

SPECS = {
    "tasks.create": (TaskCreateArgs, "workspace_tasks"),
    "tasks.complete": (TaskCompleteArgs, "workspace_tasks"),
    "notes.create": (NoteCreateArgs, "workspace_notes"),
}
LEVEL = {"public": 0, "private": 1, "sensitive": 2}


def stamp():
    return datetime.now(UTC).isoformat()


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Agency:
    def __init__(self, store: Store):
        self.store = store

    @staticmethod
    def _owner(db):
        return db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]

    @staticmethod
    def _object(db, table, item_id):
        row = db.execute(f"SELECT data_json FROM {table} WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise MemoryNotFound("Action object not found")
        return json.loads(row[0])

    @staticmethod
    def _put(db, table, item):
        db.execute(
            f"INSERT INTO {table} VALUES (?,?) ON CONFLICT(id) "
            "DO UPDATE SET data_json=excluded.data_json",
            (item["id"], json.dumps(item, ensure_ascii=False)),
        )

    def _event(self, db, plan_id, stage, outcome, code):
        self._put(
            db,
            "action_events",
            dict(
                id=uuid4().hex,
                plan_id=plan_id,
                stage=stage,
                outcome=outcome,
                code=code,
                created_at=stamp(),
            ),
        )

    def _permission(self, db, name):
        if name not in SPECS:
            raise MemoryInputError("Unknown local tool")
        row = db.execute("SELECT data_json FROM tool_permissions WHERE name=?", (name,)).fetchone()
        return (
            json.loads(row[0])
            if row
            else dict(
                tool=name,
                owner_id=self._owner(db),
                scope=SPECS[name][1],
                enabled=False,
                labels=["public", "private"],
                entity_ids=None,
                revision=1,
            )
        )

    def permissions(self):
        with self.store.connect() as db:
            return [self._permission(db, name) for name in SPECS]

    def configure(self, name, payload: PermissionInput, expected_revision: int):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = self._permission(db, name)
            if type(expected_revision) is not int or item["revision"] != expected_revision:
                raise MemoryConflict("Tool permission changed; review it again")
            if payload.entity_ids is not None:
                for entity_id in payload.entity_ids:
                    self.store._entity(db, entity_id)
            item.update(payload.model_dump())
            item["revision"] += 1
            db.execute(
                "INSERT INTO tool_permissions VALUES (?,?) ON CONFLICT(name) "
                "DO UPDATE SET data_json=excluded.data_json",
                (name, json.dumps(item)),
            )
            return item

    def _prepare(self, db, request):
        try:
            arguments = (
                SPECS[request.tool][0].model_validate(request.arguments).model_dump(mode="json")
            )
        except (KeyError, ValidationError):
            raise MemoryInputError("Tool arguments violate the registered schema") from None
        sources, entities = {}, {}
        labels = [request.sensitivity]
        target = None
        entity_ids = set()
        if arguments.get("project_id"):
            entity_ids.add(arguments["project_id"])
        if request.tool == "tasks.complete":
            target = self._object(db, "tasks", arguments["task_id"])
            if target["owner_id"] != self._owner(db):
                raise MemoryPermissionDenied("Task belongs to another owner")
            if target["revision"] != arguments["expected_revision"]:
                raise MemoryConflict("Task changed; review the current revision")
            labels.append(target["sensitivity"])
            if target.get("project_id"):
                entity_ids.add(target["project_id"])
        # Updates inherit target lineage; omitting source_ids cannot bypass a subject/label scope.
        source_ids = sorted(set(request.source_ids) | set(target["source_ids"] if target else []))
        for item_id in source_ids:
            row = db.execute("SELECT * FROM entries WHERE id=?", (item_id,)).fetchone()
            if (
                not row
                or row["owner_id"] != self._owner(db)
                or row["status"] != "confirmed"
                or row["belief"] != "known"
                or not active_at(dict(row), datetime.now(UTC))
            ):
                raise MemoryConflict("Action evidence is missing, uncertain or not current")
            sources[item_id] = row["revision"]
            labels.append(row["sensitivity"])
            if row["entity_id"]:
                entity_ids.add(row["entity_id"])
        for entity_id in sorted(entity_ids):
            entity = self.store._entity(db, entity_id)
            if entity_id == arguments.get("project_id") and entity["kind"] != "project":
                raise MemoryInputError("Tool project must be a confirmed project entity")
            entities[entity_id] = entity["revision"]
            labels.append(entity["sensitivity"])
        sensitivity = max(labels, key=LEVEL.__getitem__)
        invocation = {
            **request.model_dump(),
            "arguments": arguments,
            "sensitivity": sensitivity,
            "source_ids": source_ids,
        }
        return invocation, sources, entities

    def _authorize(self, permission, invocation, entities):
        if not permission["enabled"]:
            raise MemoryPermissionDenied("Tool is disabled; owner permission is required")
        if invocation["sensitivity"] not in permission["labels"]:
            raise MemoryPermissionDenied("Tool data label is outside its permission boundary")
        if permission["entity_ids"] is not None and not set(entities) <= set(
            permission["entity_ids"]
        ):
            raise MemoryPermissionDenied("Tool subject is outside its permission boundary")

    def plan(self, request: ToolInvocation):
        try:
            requested = request.model_dump(mode="json")
            requested["arguments"] = (
                SPECS[request.tool][0].model_validate(request.arguments).model_dump(mode="json")
            )
            serialized = json.dumps(requested, sort_keys=True, ensure_ascii=False)
            if len(serialized.encode("utf-8")) > 65536:
                raise MemoryInputError("Tool invocation exceeds the byte limit")
        except (ValidationError, UnicodeError, TypeError):
            raise MemoryInputError("Tool invocation violates the registered contract") from None
        request_digest = digest(requested)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # Key reuse is checked against the requested operation, not transient permission state.
            previous = db.execute(
                "SELECT data_json FROM action_plans WHERE idempotency_key=?",
                (request.idempotency_key,),
            ).fetchone()
            if previous:
                item = json.loads(previous[0])
                if item["request_digest"] != request_digest:
                    raise MemoryConflict("Idempotency key already describes a different operation")
                return item
            invocation, sources, entities = self._prepare(db, request)
            permission = self._permission(db, request.tool)
            if request.intent == "act":
                self._authorize(permission, invocation, entities)
            owner, now = self._owner(db), stamp()
            signature = dict(
                owner_id=owner,
                invocation=invocation,
                permission_revision=permission["revision"],
                source_revisions=sources,
                entity_revisions=entities,
            )
            item = dict(
                id=uuid4().hex,
                **signature,
                digest=digest(signature),
                request_digest=request_digest,
                revision=1,
                status="recommended" if request.intent == "recommend" else "planned",
                attempts=0,
                result=None,
                undo=None,
                approved_digest=None,
                created_at=now,
                updated_at=now,
            )
            db.execute(
                "INSERT INTO action_plans VALUES (?,?,?)",
                (item["id"], request.idempotency_key, json.dumps(item, ensure_ascii=False)),
            )
            self._event(db, item["id"], "intent", item["status"], "owner_request")
            self._event(db, item["id"], "plan", item["status"], "no_effects_yet")
            return item

    def _fresh(self, db, item):
        if item["owner_id"] != self._owner(db):
            raise MemoryPermissionDenied("Action plan belongs to another owner")
        signature = {
            field: item[field]
            for field in (
                "owner_id",
                "invocation",
                "permission_revision",
                "source_revisions",
                "entity_revisions",
            )
        }
        if digest(signature) != item["digest"]:
            raise MemoryConflict("Action plan changed; approval is invalid")
        invocation, sources, entities = self._prepare(
            db, ToolInvocation.model_validate(item["invocation"])
        )
        if (
            invocation != item["invocation"]
            or sources != item["source_revisions"]
            or entities != item["entity_revisions"]
        ):
            raise MemoryConflict("Action data changed; create and review a new plan")
        permission = self._permission(db, invocation["tool"])
        self._authorize(permission, invocation, entities)
        if permission["revision"] != item["permission_revision"]:
            raise MemoryConflict("Tool permission changed; create a new plan")

    @staticmethod
    def _save_plan(db, item):
        db.execute(
            "UPDATE action_plans SET data_json=? WHERE id=?",
            (json.dumps(item, ensure_ascii=False), item["id"]),
        )

    def approve(self, plan_id, expected_revision: int, reviewed_digest: str):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = self._object(db, "action_plans", plan_id)
            if item["status"] not in {"planned", "approved"}:
                raise MemoryConflict(
                    "Only an action plan can be approved; recommendations cannot execute"
                )
            if (
                type(expected_revision) is not int
                or item["revision"] != expected_revision
                or item["digest"] != reviewed_digest
            ):
                raise MemoryConflict("Approval must match the reviewed plan revision and digest")
            self._fresh(db, item)
            if item["status"] == "approved":
                return item
            item.update(
                status="approved",
                approved_digest=reviewed_digest,
                revision=item["revision"] + 1,
                updated_at=stamp(),
            )
            self._save_plan(db, item)
            self._event(db, plan_id, "approval", "approved", "exact_plan_digest")
            return item

    def _apply_tool(self, db, item):
        call = item["invocation"]
        args = call["arguments"]
        now = stamp()
        if call["tool"] == "tasks.complete":
            task = self._object(db, "tasks", args["task_id"])
            before = task["status"]
            changed = before != "completed"
            if changed:
                task.update(status="completed", revision=task["revision"] + 1, updated_at=now)
                self._put(db, "tasks", task)
            return {
                "table": "tasks",
                "id": task["id"],
                "revision": task["revision"],
                "changed": changed,
            }, {"before_status": before}
        table = "tasks" if call["tool"] == "tasks.create" else "notes"
        record = dict(
            id=uuid4().hex,
            **args,
            owner_id=self._owner(db),
            created_by=item["id"],
            sensitivity=call["sensitivity"],
            source_ids=call["source_ids"],
            revision=1,
            created_at=now,
            updated_at=now,
        )
        if table == "tasks":
            record["status"] = "open"
        self._put(db, table, record)
        return {"table": table, "id": record["id"], "revision": 1, "changed": True}, {}

    def execute(self, plan_id):
        attempted = False
        try:
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                item = self._object(db, "action_plans", plan_id)
                if item["status"] == "completed":
                    return item
                if (
                    item["status"] not in {"approved", "failed"}
                    or item["approved_digest"] != item["digest"]
                ):
                    raise MemoryPermissionDenied(
                        "Explicit owner approval is required before execution"
                    )
                if item["attempts"] >= 3:
                    raise MemoryConflict("Bounded retry limit reached; review a new operation")
                self._fresh(db, item)
                attempted = True
                result, undo = self._apply_tool(db, item)
                item.update(
                    status="completed",
                    result=result,
                    undo=undo,
                    attempts=item["attempts"] + 1,
                    revision=item["revision"] + 1,
                    updated_at=stamp(),
                )
                self._save_plan(db, item)
                self._event(db, plan_id, "execution", "completed", "transaction_committed")
                return item
        except (MemoryConflict, MemoryPermissionDenied, MemoryNotFound, MemoryInputError):
            with self.store.connect() as db:
                if db.execute("SELECT 1 FROM action_plans WHERE id=?", (plan_id,)).fetchone():
                    self._event(
                        db, plan_id, "execution", "blocked", "permission_or_data_precondition"
                    )
            raise
        except Exception:
            if not attempted:
                raise
            # Tool effects and the success record rolled back together.
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                item = self._object(db, "action_plans", plan_id)
                if item["status"] == "completed":
                    return item
                item.update(
                    status="failed",
                    attempts=item["attempts"] + 1,
                    revision=item["revision"] + 1,
                    updated_at=stamp(),
                )
                self._save_plan(db, item)
                self._event(db, plan_id, "execution", "failed", "tool_failure_rolled_back")
                return item

    def rollback(self, plan_id):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = self._object(db, "action_plans", plan_id)
            if item["status"] == "rolled_back":
                return item
            if item["status"] != "completed" or item["owner_id"] != self._owner(db):
                raise MemoryConflict("Only the owner's completed action can be rolled back")
            result = item["result"]
            table = "notes" if item["invocation"]["tool"] == "notes.create" else "tasks"
            if result["table"] != table:
                raise MemoryConflict("Action result does not match the registered tool")
            target = self._object(db, table, result["id"])
            if target["owner_id"] != item["owner_id"] or target["revision"] != result["revision"]:
                raise MemoryConflict("Action output changed; rollback cannot overwrite it")
            if result["changed"]:
                if item["invocation"]["tool"] == "tasks.complete":
                    target.update(
                        status=item["undo"]["before_status"],
                        revision=target["revision"] + 1,
                        updated_at=stamp(),
                    )
                    self._put(db, "tasks", target)
                else:
                    if target["created_by"] != item["id"]:
                        raise MemoryConflict("Rollback cannot delete another action's output")
                    db.execute(f"DELETE FROM {table} WHERE id=?", (result["id"],))
            item.update(status="rolled_back", revision=item["revision"] + 1, updated_at=stamp())
            self._save_plan(db, item)
            self._event(db, plan_id, "rollback", "rolled_back", "exact_effect_reversed")
            return item

    def cancel(self, plan_id):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = self._object(db, "action_plans", plan_id)
            if item["status"] == "cancelled":
                return item
            if item["status"] not in {"planned", "recommended", "approved", "failed"}:
                raise MemoryConflict("Completed actions must use rollback, not cancellation")
            item.update(status="cancelled", revision=item["revision"] + 1, updated_at=stamp())
            self._save_plan(db, item)
            self._event(db, plan_id, "cancellation", "cancelled", "no_effects")
            return item

    def plans(self):
        with self.store.connect() as db:
            return records(db, "action_plans")[-100:]

    def events(self, plan_id):
        with self.store.connect() as db:
            self._object(db, "action_plans", plan_id)
            return [item for item in records(db, "action_events") if item["plan_id"] == plan_id]

    def tasks(self):
        with self.store.connect() as db:
            return records(db, "tasks")

    def notes(self):
        with self.store.connect() as db:
            return records(db, "notes")
