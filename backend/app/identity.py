"""Owner-reviewed entity identity and evidence-linked relationships; no graph dependency."""

import json
import unicodedata
from datetime import UTC, datetime
from uuid import uuid4

from .identity_schema import records
from .memory import MemoryConflict, MemoryInputError, MemoryNotFound, Store
from .memory_models import EntityInput, RelationshipInput, TemporalQuery

LEVEL = {"public": 0, "private": 1, "sensitive": 2}


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
            item.update({field: getattr(payload, field) for field in payload.model_fields_set})
            item.update(
                status="pending",
                revision=item["revision"] + 1,
                updated_at=datetime.now(UTC).isoformat(),
            )
            self._write(db, "entities", item, "edited")
            return item

    def confirm(self, item_id, expected_revision: int, *, relationship=False):
        table = "relationships" if relationship else "entities"
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = self._get(db, table, item_id)
            if type(expected_revision) is not int or item["revision"] != expected_revision:
                raise MemoryConflict("Identity record changed; review its current revision")
            if relationship:
                self.store._entity(db, item["from_entity_id"])
                self.store._entity(db, item["to_entity_id"])
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

    def relate(self, payload: RelationshipInput):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            left = self.store._entity(db, payload.from_entity_id)
            right = self.store._entity(db, payload.to_entity_id)
            if left["id"] == right["id"]:
                raise MemoryInputError("A relationship must connect distinct entities")
            evidence = db.execute(
                "SELECT * FROM entries WHERE id=?", (payload.evidence_id,)
            ).fetchone()
            if not evidence or evidence["status"] != "confirmed":
                raise MemoryConflict("Relationship requires confirmed memory evidence")
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

    def delete(self, item_id, *, relationship=False):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            table = "relationships" if relationship else "entities"
            if not relationship:
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
