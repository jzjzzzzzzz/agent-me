"""Owner-reviewed entity identity and evidence-linked relationships; no graph dependency."""

import hashlib
import json
import unicodedata
from datetime import UTC, datetime
from uuid import uuid4

from .identity_schema import records
from .memory import MemoryConflict, MemoryInputError, MemoryNotFound, Store
from .memory_models import EntityInput, IdentityDelete, RelationshipInput, TemporalQuery

LEVEL = {"public": 0, "private": 1, "sensitive": 2}
_UNSET = object()


def canonical_alias(value):
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


class IdentityStore:
    def __init__(self, store: Store):
        self.store = store

    @staticmethod
    def _get(db, table, item_id):
        row = db.execute(f"SELECT data_json FROM {table} WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise MemoryNotFound("Identity record not found")
        return json.loads(row[0])

    @staticmethod
    def _write(db, table, item, change):
        db.execute(
            f"INSERT INTO {table} VALUES (?,?) ON CONFLICT(id) DO UPDATE "
            "SET data_json=excluded.data_json",
            (item["id"], json.dumps(item)),
        )
        db.execute(
            f"INSERT INTO {table}_revisions VALUES (?,?,?)",
            (item["id"], item["revision"], json.dumps({**item, "change": change})),
        )

    def entities(self):
        with self.store.connect() as db:
            return records(db, "entities")

    def owner(self):
        with self.store.connect() as db:
            db.execute("BEGIN")
            row = db.execute("SELECT value FROM workspace WHERE key='owner_entity_id'").fetchone()
            return {
                "owner_id": db.execute(
                    "SELECT value FROM workspace WHERE key='owner_id'"
                ).fetchone()[0],
                "entity_id": row[0] if row else None,
            }

    def bind_owner(
        self,
        entity_id: str | None,
        *,
        expected_owner_entity_id=_UNSET,
        expected_entity_revision: int | None = None,
    ):
        if expected_entity_revision is not None and (
            type(expected_entity_revision) is not int or expected_entity_revision < 1
        ):
            raise MemoryInputError("Invalid owner target revision")
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute(
                "SELECT value FROM workspace WHERE key='owner_entity_id'"
            ).fetchone()
            if expected_owner_entity_id is not _UNSET and expected_owner_entity_id != (
                current[0] if current else None
            ):
                raise MemoryConflict("Owner binding changed; review it again")
            if entity_id is None:
                if expected_entity_revision is not None:
                    raise MemoryInputError("Unbinding has no target entity revision")
                db.execute("DELETE FROM workspace WHERE key='owner_entity_id'")
            else:
                item = self.store._entity(db, entity_id)
                if item["kind"] != "person":
                    raise MemoryInputError("Owner identity must be a confirmed person")
                if (
                    expected_entity_revision is not None
                    and item["revision"] != expected_entity_revision
                ):
                    raise MemoryConflict("Owner target changed; review its current revision")
                db.execute(
                    "INSERT INTO workspace VALUES ('owner_entity_id',?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (entity_id,),
                )
            return {
                "owner_id": db.execute(
                    "SELECT value FROM workspace WHERE key='owner_id'"
                ).fetchone()[0],
                "entity_id": entity_id,
            }

    def add(self, payload: EntityInput, *, distinct: bool = False):
        if type(distinct) is not bool:
            raise MemoryInputError("Distinct identity requires an explicit boolean")
        aliases = {canonical_alias(name) for name in [payload.name, *payload.aliases]}
        now = datetime.now(UTC).isoformat()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not distinct:
                for item in records(db, "entities"):
                    if (
                        item["kind"] == payload.kind
                        and item["sensitivity"] == payload.sensitivity
                        and {canonical_alias(name) for name in [item["name"], *item["aliases"]]}
                        == aliases
                    ):
                        return item
            owner = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
            item = dict(
                id=uuid4().hex,
                **payload.model_dump(),
                owner_id=owner,
                source="manual",
                status="pending",
                revision=1,
                created_at=now,
                updated_at=now,
            )
            self._write(db, "entities", item, "created")
            return item

    def edit(self, entity_id, payload: EntityInput, expected_revision: int):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = self._get(db, "entities", entity_id)
            if type(expected_revision) is not int or item["revision"] != expected_revision:
                raise MemoryConflict("Entity changed; review its current revision")
            owner = db.execute("SELECT value FROM workspace WHERE key='owner_entity_id'").fetchone()
            if owner and owner[0] == entity_id and payload.kind != "person":
                raise MemoryInputError("Unbind the owner before changing its entity kind")
            item.update({field: getattr(payload, field) for field in payload.model_fields_set})
            item.update(
                status="pending",
                revision=item["revision"] + 1,
                updated_at=datetime.now(UTC).isoformat(),
            )
            self._write(db, "entities", item, "edited")
            return item

    def confirm(
        self, item_id, expected_revision: int, *, relationship=False, expected_entity_revisions=None
    ):
        table = "relationships" if relationship else "entities"
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = self._get(db, table, item_id)
            if type(expected_revision) is not int or item["revision"] != expected_revision:
                raise MemoryConflict("Identity record changed; review its current revision")
            if relationship:
                self._review_entities(db, item, expected_entity_revisions)
                evidence = db.execute(
                    "SELECT * FROM entries WHERE id=?", (item["evidence_id"],)
                ).fetchone()
                if (
                    not evidence
                    or evidence["status"] != "confirmed"
                    or evidence["revision"] != item["evidence_revision"]
                ):
                    raise MemoryConflict("Relationship evidence changed; create a new proposal")
            if item["status"] == "confirmed":
                return item
            item.update(
                status="confirmed",
                revision=item["revision"] + 1,
                updated_at=datetime.now(UTC).isoformat(),
            )
            self._write(db, table, item, "confirmed")
            return item

    def history(self, item_id, *, relationship=False):
        table = "relationships" if relationship else "entities"
        with self.store.connect() as db:
            db.execute("BEGIN")
            self._get(db, table, item_id)
            return [
                json.loads(row[0])
                for row in db.execute(
                    f"SELECT data_json FROM {table}_revisions WHERE id=? ORDER BY revision",
                    (item_id,),
                )
            ]

    def resolve(self, name: str, *, kind=None, allow_sensitive=False):
        if type(allow_sensitive) is not bool:
            raise MemoryInputError("Sensitive identity disclosure requires an explicit boolean")
        matches = [
            item
            for item in self.entities()
            if item["status"] == "confirmed"
            and (kind is None or item["kind"] == kind)
            and (allow_sensitive or item["sensitivity"] != "sensitive")
            and canonical_alias(name)
            in {canonical_alias(alias) for alias in [item["name"], *item["aliases"]]}
        ]
        return {
            "status": "resolved" if len(matches) == 1 else "ambiguous" if matches else "unknown",
            "matches": matches,
        }

    def relationships(self):
        with self.store.connect() as db:
            return records(db, "relationships")

    def _review_entities(self, db, item, expected_entity_revisions):
        endpoints = (item["from_entity_id"], item["to_entity_id"])
        if expected_entity_revisions is not None and (
            not isinstance(expected_entity_revisions, dict)
            or set(expected_entity_revisions) != set(endpoints)
            or any(
                type(value) is not int or value < 1 for value in expected_entity_revisions.values()
            )
        ):
            raise MemoryInputError("Review revisions for exactly both relationship endpoints")
        records = [self.store._entity(db, entity_id) for entity_id in endpoints]
        if expected_entity_revisions is not None and any(
            item["revision"] != expected_entity_revisions[item["id"]] for item in records
        ):
            raise MemoryConflict("Relationship endpoint changed; review it again")
        return records

    def relate(
        self,
        payload: RelationshipInput,
        *,
        expected_evidence_revision: int | None = None,
        expected_entity_revisions=None,
    ):
        if expected_evidence_revision is not None and (
            type(expected_evidence_revision) is not int or expected_evidence_revision < 1
        ):
            raise MemoryInputError("Invalid relationship evidence revision")
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            left, right = self._review_entities(db, payload.model_dump(), expected_entity_revisions)
            if left["id"] == right["id"]:
                raise MemoryInputError("A relationship must connect distinct entities")
            evidence = db.execute(
                "SELECT * FROM entries WHERE id=?", (payload.evidence_id,)
            ).fetchone()
            if not evidence or evidence["status"] != "confirmed":
                raise MemoryConflict("Relationship requires confirmed memory evidence")
            if (
                expected_evidence_revision is not None
                and evidence["revision"] != expected_evidence_revision
            ):
                raise MemoryConflict("Relationship evidence changed; review it again")
            for previous in records(db, "relationships"):
                if (
                    all(
                        previous[key] == getattr(payload, key)
                        for key in ("from_entity_id", "to_entity_id", "predicate", "evidence_id")
                    )
                    and previous["evidence_revision"] == evidence["revision"]
                ):
                    return previous
            now = datetime.now(UTC).isoformat()
            item = dict(
                id=uuid4().hex,
                **payload.model_dump(),
                owner_id=left["owner_id"],
                evidence_revision=evidence["revision"],
                status="pending",
                revision=1,
                created_at=now,
                updated_at=now,
            )
            item["sensitivity"] = max(
                (
                    payload.sensitivity,
                    left["sensitivity"],
                    right["sensitivity"],
                    evidence["sensitivity"],
                ),
                key=LEVEL.__getitem__,
            )
            self._write(db, "relationships", item, "created")
            return item

    def neighbours(self, entity_id, *, allow_sensitive=False):
        query = TemporalQuery(allow_sensitive=allow_sensitive)
        eligible = {item["record"]["id"]: item["record"] for item in self.store.select(query)}
        entities = {
            item["id"]: item
            for item in self.entities()
            if item["status"] == "confirmed"
            and (allow_sensitive or item["sensitivity"] != "sensitive")
        }
        if entity_id not in entities:
            return {"entities": [], "relationships": []}
        related = []
        ids = {entity_id}
        for item in self.relationships():
            evidence = eligible.get(item["evidence_id"])
            if (
                item["status"] != "confirmed"
                or not evidence
                or evidence["revision"] != item["evidence_revision"]
                or item["from_entity_id"] not in entities
                or item["to_entity_id"] not in entities
                or (item["sensitivity"] == "sensitive" and not allow_sensitive)
                or entity_id not in (item["from_entity_id"], item["to_entity_id"])
            ):
                continue
            if len(related) >= 64 or len(ids | {item["from_entity_id"], item["to_entity_id"]}) > 32:
                break
            related.append(item)
            ids.update((item["from_entity_id"], item["to_entity_id"]))
        return {
            "entities": [entities[item_id] for item_id in sorted(ids)],
            "relationships": related,
        }

    def _delete_scope(self, db, item_id, *, relationship=False):
        table = "relationships" if relationship else "entities"
        item = self._get(db, table, item_id)
        memories, sources, runs, edges = [], [], [], []
        if not relationship:
            memories = [
                dict(row)
                for row in db.execute(
                    "SELECT DISTINCT e.* FROM entries e LEFT JOIN revisions r ON r.id=e.id "
                    "WHERE e.entity_id=? OR r.entity_id=? ORDER BY e.id",
                    (item_id, item_id),
                )
            ]
            sources = [
                {**dict(row), "approved": bool(row["approved"])}
                for row in db.execute(
                    "SELECT * FROM sources WHERE entity_id=? ORDER BY id", (item_id,)
                )
            ]
            source_ids = {row["id"] for row in sources}
            runs = sorted(
                (
                    json.loads(row[0])
                    for row in db.execute("SELECT run_json FROM ingestion_runs")
                    if json.loads(row[0])["source_id"] in source_ids
                ),
                key=lambda run: run["id"],
            )
            memory_ids = {row["id"] for row in memories}
            edges = sorted(
                (
                    edge
                    for edge in records(db, "relationships")
                    if item_id in (edge["from_entity_id"], edge["to_entity_id"])
                    or edge["evidence_id"] in memory_ids
                ),
                key=lambda edge: edge["id"],
            )
        else:
            source_ids, memory_ids = set(), set()
        origins = [
            dict(row)
            for row in db.execute("SELECT * FROM origins ORDER BY id")
            if row["memory_id"] in memory_ids or row["source_id"] in source_ids
        ]
        history = []
        for entity in [item, *edges]:
            history_table = table if entity is item else "relationships"
            history.extend(
                json.loads(row[0])
                for row in db.execute(
                    f"SELECT data_json FROM {history_table}_revisions WHERE id=? ORDER BY revision",
                    (entity["id"],),
                )
            )
        for memory in memories:
            history.extend(
                dict(row)
                for row in db.execute(
                    "SELECT * FROM revisions WHERE id=? ORDER BY revision", (memory["id"],)
                )
            )
        owner = db.execute("SELECT value FROM workspace WHERE key='owner_entity_id'").fetchone()
        preview = dict(
            kind="relationship" if relationship else "entity",
            record=item,
            memories=memories,
            sources=sources,
            runs=runs,
            relationships=edges,
            owner_binding=bool(not relationship and owner and owner[0] == item_id),
            origin_count=len(origins),
            history_count=len(history),
        )
        fingerprint = json.dumps([preview, origins, history], sort_keys=True, ensure_ascii=False)
        return {**preview, "digest": hashlib.sha256(fingerprint.encode()).hexdigest()}

    def preview_delete(self, item_id, *, relationship=False):
        with self.store.connect() as db:
            db.execute("BEGIN")
            return self._delete_scope(db, item_id, relationship=relationship)

    def delete(self, item_id, *, relationship=False, expected_revision=None, digest=None):
        IdentityDelete(expected_revision=expected_revision, digest=digest)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            table = "relationships" if relationship else "entities"
            if expected_revision is not None:
                item = self._get(db, table, item_id)
                if item["revision"] != expected_revision:
                    raise MemoryConflict("Identity record changed; review it again")
            if (
                digest is not None
                and self._delete_scope(db, item_id, relationship=relationship)["digest"] != digest
            ):
                raise MemoryConflict("Deletion scope changed; preview it again")
            if not relationship:
                db.execute(
                    "DELETE FROM workspace WHERE key='owner_entity_id' AND value=?", (item_id,)
                )
                for row in db.execute(
                    "SELECT DISTINCT e.id FROM entries e LEFT JOIN revisions r ON r.id=e.id "
                    "WHERE e.entity_id=? OR r.entity_id=?",
                    (item_id, item_id),
                ).fetchall():
                    self.store._delete(db, row["id"])
                source_ids = {
                    row[0]
                    for row in db.execute("SELECT id FROM sources WHERE entity_id=?", (item_id,))
                }
                for source_id in source_ids:
                    db.execute("DELETE FROM origins WHERE source_id=?", (source_id,))
                    db.execute("DELETE FROM sources WHERE id=?", (source_id,))
                for row in db.execute("SELECT id,run_json FROM ingestion_runs").fetchall():
                    if json.loads(row["run_json"])["source_id"] in source_ids:
                        db.execute("DELETE FROM ingestion_runs WHERE id=?", (row["id"],))
                for edge in records(db, "relationships"):
                    if item_id in (edge["from_entity_id"], edge["to_entity_id"]):
                        db.execute("DELETE FROM relationships WHERE id=?", (edge["id"],))
                        db.execute("DELETE FROM relationships_revisions WHERE id=?", (edge["id"],))
            db.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
            db.execute(f"DELETE FROM {table}_revisions WHERE id=?", (item_id,))
        return {"deleted": True}
