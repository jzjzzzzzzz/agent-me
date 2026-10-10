"""Local memory lifecycle and retrieval, usable without an HTTP server or model provider."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from .agency_schema import extend_agency
from .control_schema import extend_control
from .identity_schema import extend_identity, extend_records, records
from .knowledge import Document, Match
from .memory_models import Confirm, EditEntry, Entry, RestoreMemory, TemporalQuery
from .memory_time import active_at, iso, overlaps, utc
from .text import normalized_tokens

_SCHEMA_VERSION = 8
_MAX_MATCHES = 20
_MAX_PREFERENCE_MATCHES = 5
_RECORD_COLUMNS = (
    "id,kind,key,content,source,status,created_at,updated_at,revision,superseded_by,sensitivity,"
    "entity_id,confidence,belief,valid_from,valid_until,occurred_at,owner_id,category"
)


def memory_digest(
    kind: str,
    key: str,
    content: str,
    *,
    entity_id=None,
    occurred_at=None,
    valid_from=None,
    valid_until=None,
) -> str:
    """Exact normalized identity, not a semantic-equivalence or truth judgement."""
    values = [
        unicodedata.normalize("NFC", value.strip().replace("\r\n", "\n"))
        for value in (kind, key, content)
    ]
    qualifiers = [entity_id, iso(occurred_at), iso(valid_from), iso(valid_until)]
    if any(value is not None for value in qualifiers):
        values.append(qualifiers)
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode("utf-8")).hexdigest()


def record_digest(item):
    return memory_digest(
        item["kind"],
        item["key"],
        item["content"],
        **{
            field: item.get(field)
            for field in ("entity_id", "occurred_at", "valid_from", "valid_until")
        },
    )


class MemoryError(Exception):
    """Domain failure; transports decide how to expose it to their callers."""


class MemoryNotFound(MemoryError):
    pass


class MemoryPermissionDenied(MemoryError):
    pass


class MemoryInputError(MemoryError):
    pass


class MemoryConflict(MemoryError):
    def __init__(self, message: str, *, conflicts: dict[str, int] | None = None):
        super().__init__(message)
        self.conflicts = conflicts


class Store:
    def __init__(self, directory: str):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "twin.sqlite3"
        if self.path.is_symlink():
            raise ValueError("Database must not be a symbolic link")
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > _SCHEMA_VERSION:
                raise ValueError("Memory database schema is newer than this application")
            if version < _SCHEMA_VERSION:
                # Recheck after taking the lock: another worker may have migrated it.
                db.execute("BEGIN IMMEDIATE")
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if version > _SCHEMA_VERSION:
                    raise ValueError("Memory database schema is newer than this application")
                if version < _SCHEMA_VERSION:
                    self._migrate(db)
                    db.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
        self.path.chmod(0o600)

    @staticmethod
    def _migrate(db):
        # Keep only the known legacy state; never fabricate pre-migration history.
        db.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, key TEXT NOT NULL,
                content TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1, superseded_by TEXT,
                sensitivity TEXT NOT NULL DEFAULT 'private'
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS turns (
                id TEXT PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(entries)")}
        if "revision" not in columns:
            db.execute("ALTER TABLE entries ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")
        if "superseded_by" not in columns:
            db.execute("ALTER TABLE entries ADD COLUMN superseded_by TEXT")
        if "sensitivity" not in columns:
            db.execute("ALTER TABLE entries ADD COLUMN sensitivity TEXT NOT NULL DEFAULT 'private'")
        db.execute("""
            CREATE TABLE IF NOT EXISTS revisions (
                id TEXT NOT NULL, kind TEXT NOT NULL, key TEXT NOT NULL,
                content TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                revision INTEGER NOT NULL, superseded_by TEXT, change TEXT NOT NULL,
                sensitivity TEXT NOT NULL DEFAULT 'private',
                PRIMARY KEY (id, revision)
            )
        """)
        if "sensitivity" not in {row["name"] for row in db.execute("PRAGMA table_info(revisions)")}:
            db.execute(
                "ALTER TABLE revisions ADD COLUMN sensitivity TEXT NOT NULL DEFAULT 'private'"
            )
        extend_records(db)
        columns = ",".join(f"e.{column}" for column in _RECORD_COLUMNS.split(","))
        db.execute(f"""
            INSERT INTO revisions ({_RECORD_COLUMNS},change)
            SELECT {columns}, 'baseline' FROM entries e
            WHERE NOT EXISTS (SELECT 1 FROM revisions r WHERE r.id=e.id)
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS memory_digests (
                memory_id TEXT PRIMARY KEY, digest TEXT NOT NULL
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS memory_digest_lookup ON memory_digests(digest)")
        db.executemany(
            "INSERT OR REPLACE INTO memory_digests VALUES (?,?)",
            [(row["id"], record_digest(dict(row))) for row in db.execute("SELECT * FROM entries")],
        )
        db.execute("""
            CREATE TABLE IF NOT EXISTS forgotten (
                digest TEXT PRIMARY KEY, forgotten_at TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
                sensitivity TEXT NOT NULL, approved INTEGER NOT NULL,
                revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_runs (
                id TEXT PRIMARY KEY, replay_key TEXT UNIQUE NOT NULL, run_json TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS origins (
                id TEXT PRIMARY KEY, memory_id TEXT NOT NULL, memory_revision INTEGER NOT NULL,
                source_id TEXT NOT NULL, source_revision INTEGER NOT NULL,
                document_hash TEXT NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL,
                excerpt TEXT NOT NULL, run_id TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE (memory_id,source_id,document_hash,start,end)
            )
        """)
        extend_identity(db)
        extend_agency(db)
        extend_control(db)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row

        def compare_keys(left, right):
            left, right = (unicodedata.normalize("NFC", value) for value in (left, right))
            return (left > right) - (left < right)

        db.create_collation("NFC", compare_keys)
        db.execute("PRAGMA secure_delete=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def entries(self, include_superseded: bool = False):
        with self.connect() as db:
            query = "SELECT * FROM entries"
            if not include_superseded:
                query += " WHERE status!='superseded'"
            return [dict(r) for r in db.execute(query + " ORDER BY rowid")]

    @property
    def owner_id(self):
        with self.connect() as db:
            return db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]

    @staticmethod
    def _entity(db, entity_id):
        if entity_id is None:
            return None
        row = db.execute("SELECT data_json FROM entities WHERE id=?", (entity_id,)).fetchone()
        if not row:
            raise MemoryNotFound("Entity not found")
        entity = json.loads(row[0])
        if entity["status"] != "confirmed":
            raise MemoryConflict("Entity must be confirmed before linking memory")
        owner = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
        if entity["owner_id"] != owner:
            raise MemoryPermissionDenied("Entity belongs to another workspace owner")
        return entity

    @staticmethod
    def _conflicts(db, item):
        return {
            row["id"]: row["revision"]
            for row in db.execute(
                "SELECT * FROM entries WHERE kind=? AND key=? COLLATE NFC "
                "AND entity_id IS ? AND status='confirmed' AND id!=?",
                (item["kind"], item["key"], item.get("entity_id"), item["id"]),
            )
            if overlaps(dict(row), item)
        }

    def export(self):
        # An explicit read transaction pins all tables to the same SQLite snapshot.
        with self.connect() as db:
            db.execute("BEGIN")
            entries = [
                dict(r) for r in db.execute(f"SELECT {_RECORD_COLUMNS} FROM entries ORDER BY rowid")
            ]
            turns = [dict(r) for r in db.execute("SELECT * FROM turns ORDER BY rowid")]
            revisions = [dict(r) for r in db.execute("SELECT * FROM revisions ORDER BY rowid")]
            sources = [
                {**dict(r), "approved": bool(r["approved"])}
                for r in db.execute("SELECT * FROM sources ORDER BY rowid")
            ]
            runs = [
                json.loads(r[0])
                for r in db.execute("SELECT run_json FROM ingestion_runs ORDER BY rowid")
            ]
            origins = [dict(r) for r in db.execute("SELECT * FROM origins ORDER BY rowid")]
            forgotten = [dict(r) for r in db.execute("SELECT * FROM forgotten ORDER BY rowid")]
            owner_id = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
            owner_entity = db.execute(
                "SELECT value FROM workspace WHERE key='owner_entity_id'"
            ).fetchone()
            entities = records(db, "entities")
            entity_revisions = records(db, "entities_revisions")
            relationships = records(db, "relationships")
            relationship_revisions = records(db, "relationships_revisions")
            retention_policy = {
                "revision": int(
                    db.execute(
                        "SELECT value FROM workspace WHERE key='retention_revision'"
                    ).fetchone()[0]
                ),
                "policy": json.loads(
                    db.execute(
                        "SELECT value FROM workspace WHERE key='retention_policy'"
                    ).fetchone()[0]
                ),
            }
            retention_plans = records(db, "retention_plans")
            permissions = [
                json.loads(row[0])
                for row in db.execute("SELECT data_json FROM tool_permissions ORDER BY name")
            ]
            plans = records(db, "action_plans")
            tasks = records(db, "tasks")
            notes = records(db, "notes")
            events = records(db, "action_events")
            from .learning_policy import settings as learning_settings

            learning_policy = learning_settings(db)
            consolidation_plans = records(db, "consolidation_plans")
            audit_events = records(db, "audit_events")
            import_archives = records(db, "import_archives")
            replay_keys = [
                dict(run_id=row[0], key=row[1])
                for row in db.execute("SELECT id,replay_key FROM ingestion_runs ORDER BY rowid")
            ]
            from .disclosure import settings as disclosure_settings

            disclosure_policy = disclosure_settings(db)
        return {
            "version": 8,
            "owner_id": owner_id,
            "owner_entity_id": owner_entity[0] if owner_entity else None,
            "entries": entries,
            "history": turns,
            "revisions": revisions,
            "sources": sources,
            "ingestion_runs": runs,
            "origins": origins,
            "forgotten": forgotten,
            "entities": entities,
            "entity_revisions": entity_revisions,
            "relationships": relationships,
            "relationship_revisions": relationship_revisions,
            "retention_policy": retention_policy,
            "retention_plans": retention_plans,
            "tool_permissions": permissions,
            "action_plans": plans,
            "tasks": tasks,
            "notes": notes,
            "action_events": events,
            "learning_policy": learning_policy,
            "consolidation_plans": consolidation_plans,
            "audit_events": audit_events,
            "import_archives": import_archives,
            "ingestion_replay_keys": replay_keys,
            "disclosure_policy": disclosure_policy,
        }

    @staticmethod
    def _snapshot(db, entry_id: str, change: str):
        db.execute(
            f"INSERT INTO revisions ({_RECORD_COLUMNS},change) "
            f"SELECT {_RECORD_COLUMNS},? FROM entries WHERE id=?",
            (change, entry_id),
        )

    @staticmethod
    def _reviewable(db, entry_id: str, expected_revision: int | None):
        item = db.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone()
        if not item:
            raise MemoryNotFound("Memory not found")
        if item["status"] == "superseded":
            raise MemoryConflict("Superseded memories are read-only; create a new candidate")
        if expected_revision is not None and item["revision"] != expected_revision:
            raise MemoryConflict("Memory changed; refresh before reviewing")
        return item

    def revisions(self, entry_id: str):
        with self.connect() as db:
            db.execute("BEGIN")
            if not db.execute("SELECT 1 FROM entries WHERE id=?", (entry_id,)).fetchone():
                raise MemoryNotFound("Memory not found")
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM revisions WHERE id=? ORDER BY revision", (entry_id,)
                )
            ]

    def _insert(self, db, entry: Entry, source: str):
        now = datetime.now(UTC).isoformat()
        entity = self._entity(db, entry.entity_id)
        sensitivity = max(
            (entry.sensitivity, entity["sensitivity"] if entity else "public"),
            key={"public": 0, "private": 1, "sensitive": 2}.__getitem__,
        )
        item = dict(
            id=uuid4().hex,
            kind=entry.kind,
            key=entry.key,
            content=entry.content,
            source=source,
            status="pending",
            created_at=now,
            updated_at=now,
            revision=1,
            superseded_by=None,
            sensitivity=sensitivity,
            entity_id=entry.entity_id,
            confidence=entry.confidence,
            belief=entry.belief,
            valid_from=iso(entry.valid_from),
            valid_until=iso(entry.valid_until),
            occurred_at=iso(entry.occurred_at),
            owner_id=db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0],
            category="episodic"
            if entry.kind in {"event", "decision"}
            else "preference"
            if entry.kind == "preference"
            else "semantic",
        )
        db.execute(
            f"INSERT INTO entries ({_RECORD_COLUMNS}) VALUES "
            "(:id,:kind,:key,:content,:source,:status,"
            ":created_at,:updated_at,:revision,:superseded_by,:sensitivity,"
            ":entity_id,:confidence,:belief,:valid_from,:valid_until,:occurred_at,:owner_id,:category)",
            item,
        )
        self._snapshot(db, item["id"], "created")
        db.execute(
            "INSERT INTO memory_digests VALUES (?,?)",
            (item["id"], record_digest(item)),
        )
        return item

    def add(self, entry: Entry, source: str = "manual"):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._insert(db, entry, source)

    def restore(self, entry_id: str, revision: int, expected_revision: int | None = None):
        RestoreMemory(revision=revision, expected_revision=expected_revision)
        # Restoring is a new proposal, never an implicit reactivation of old evidence.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone()
            if not current:
                raise MemoryNotFound("Memory not found")
            if expected_revision is not None and current["revision"] != expected_revision:
                raise MemoryConflict("Memory changed; refresh before restoring")
            item = db.execute(
                "SELECT * FROM revisions WHERE id=? AND revision=?", (entry_id, revision)
            ).fetchone()
            if not item:
                raise MemoryNotFound("Memory revision not found")
            entry = Entry(
                kind=item["kind"],
                key=item["key"],
                content=item["content"],
                sensitivity=max(
                    (current["sensitivity"], item["sensitivity"]),
                    key={"public": 0, "private": 1, "sensitive": 2}.__getitem__,
                ),
                **{
                    field: item[field]
                    for field in (
                        "entity_id",
                        "confidence",
                        "belief",
                        "valid_from",
                        "valid_until",
                        "occurred_at",
                    )
                },
            )
            return self._insert(db, entry, source=f"memory:{entry_id}@{revision}")

    def edit(self, entry_id: str, entry: Entry, expected_revision: int | None = None):
        EditEntry(
            kind=entry.kind,
            key=entry.key,
            content=entry.content,
            expected_revision=expected_revision,
        )
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = self._reviewable(db, entry_id, expected_revision)
            data = {field: item[field] for field in Entry.model_fields}
            data.update(
                {
                    field: getattr(entry, field)
                    for field in Entry.model_fields
                    if field in entry.model_fields_set
                }
            )
            # Core callers may deliberately change kind/content; defaults aren't a request
            # to erase metadata that an older client does not understand.
            data.update(kind=entry.kind, key=entry.key, content=entry.content)
            try:
                checked = Entry.model_validate(data)
            except ValidationError:
                raise MemoryInputError(
                    "Edited metadata is incompatible; explicitly clear conflicting time fields"
                ) from None
            entity = self._entity(db, checked.entity_id)
            data = checked.model_dump(mode="json")
            data["sensitivity"] = max(
                (checked.sensitivity, entity["sensitivity"] if entity else "public"),
                key={"public": 0, "private": 1, "sensitive": 2}.__getitem__,
            )
            for field in ("valid_from", "valid_until", "occurred_at"):
                data[field] = iso(getattr(checked, field))
            data.update(
                id=entry_id,
                updated_at=datetime.now(UTC).isoformat(),
                category="episodic"
                if checked.kind in {"event", "decision"}
                else "preference"
                if checked.kind == "preference"
                else "semantic",
            )
            db.execute(
                "UPDATE entries SET kind=:kind,key=:key,content=:content,source='manual',"
                "status='pending',"
                "updated_at=:updated_at,revision=revision+1,sensitivity=:sensitivity,entity_id=:entity_id,"
                "confidence=:confidence,belief=:belief,valid_from=:valid_from,valid_until=:valid_until,"
                "occurred_at=:occurred_at,category=:category WHERE id=:id",
                data,
            )
            self._snapshot(db, entry_id, "edited")
            db.execute(
                "UPDATE memory_digests SET digest=? WHERE memory_id=?",
                (record_digest(data), entry_id),
            )
        return {"status": "pending", "revision": item["revision"] + 1}

    def confirm(
        self,
        entry_id: str,
        replace_ids: list[str],
        expected_revision: int | None = None,
        replace_revisions: dict[str, int] | None = None,
    ):
        Confirm(
            replace_ids=replace_ids,
            expected_revision=expected_revision,
            replace_revisions=replace_revisions,
        )
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = self._reviewable(db, entry_id, expected_revision)
            entity = self._entity(db, item["entity_id"])
            from .learning_policy import matches_prefix
            from .learning_policy import settings as learning_settings

            policy = learning_settings(db)["policy"]
            labels = {item["sensitivity"], entity["sensitivity"] if entity else "public"}
            strict_review = bool(labels & set(policy["require_revision_labels"])) or matches_prefix(
                item["key"], policy["require_revision_key_prefixes"]
            )
            if strict_review and expected_revision is None:
                raise MemoryPermissionDenied("Learning policy requires revision-bound owner review")
            conflict_revisions = self._conflicts(db, dict(item))
            conflicts = list(conflict_revisions)
            if strict_review and conflicts and replace_revisions is None:
                raise MemoryPermissionDenied(
                    "Learning policy requires revision-bound replacement review"
                )
            if set(conflicts) != set(replace_ids):
                raise MemoryConflict(
                    "Confirm replacement of conflicting memories", conflicts=conflict_revisions
                )
            if replace_revisions is not None and replace_revisions != conflict_revisions:
                raise MemoryConflict("Conflicting memories changed; refresh before replacing")
            # Repeating a successful confirmation does not fabricate another revision.
            if item["status"] == "confirmed":
                return {"status": "confirmed", "revision": item["revision"]}
            now = datetime.now(UTC).isoformat()
            for old_id in conflicts:
                db.execute(
                    "UPDATE entries SET status='superseded',superseded_by=?,updated_at=?,"
                    "revision=revision+1 WHERE id=?",
                    (entry_id, now, old_id),
                )
                self._snapshot(db, old_id, "superseded")
            db.execute(
                "UPDATE entries SET status='confirmed',updated_at=?,revision=revision+1 WHERE id=?",
                (now, entry_id),
            )
            self._snapshot(db, entry_id, "confirmed")
        return {"status": "confirmed", "revision": item["revision"] + 1}

    def delete(self, entry_id: str):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._delete(db, entry_id)
        return {"deleted": True}

    @staticmethod
    def _delete(db, entry_id):
        for row in db.execute("SELECT * FROM revisions WHERE id=?", (entry_id,)).fetchall():
            db.execute(
                "INSERT OR REPLACE INTO forgotten VALUES (?,?)",
                (
                    record_digest(dict(row)),
                    datetime.now(UTC).isoformat(),
                ),
            )
        db.execute("DELETE FROM origins WHERE memory_id=?", (entry_id,))
        db.execute("DELETE FROM memory_digests WHERE memory_id=?", (entry_id,))
        db.execute("DELETE FROM revisions WHERE id=?", (entry_id,))
        db.execute("DELETE FROM entries WHERE id=?", (entry_id,))
        for relation in records(db, "relationships"):
            if relation["evidence_id"] == entry_id:
                db.execute("DELETE FROM relationships_revisions WHERE id=?", (relation["id"],))
                db.execute("DELETE FROM relationships WHERE id=?", (relation["id"],))

    def history(self):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM turns ORDER BY rowid DESC LIMIT 100").fetchall()
            return [dict(r) for r in reversed(rows)]

    def clear_history(self):
        with self.connect() as db:
            db.execute("DELETE FROM turns")
        return {"deleted": True}

    def save_chat(self, question: str, answer: str, *, expected_owner_id: str | None = None):
        turn_id = uuid4().hex
        candidate: Entry | None = None
        # Explicit syntax only: do not silently infer personal facts from casual conversation.
        for prefix in ("记住：", "记住:", "Remember:", "remember:"):
            if question.startswith(prefix):
                value = question[len(prefix) :].strip()
                if value:
                    candidate = Entry(
                        kind="preference", key="conversation.preference", content=value[:2000]
                    )
                break
        # The source turn, candidate, and its initial snapshot must succeed together.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                expected_owner_id is not None
                and db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
                != expected_owner_id
            ):
                raise MemoryConflict("Workspace changed during chat; discarded stale result")
            now = datetime.now(UTC).isoformat()
            db.executemany(
                "INSERT INTO turns VALUES (?,?,?,?)",
                [(turn_id, "user", question, now), (uuid4().hex, "assistant", answer, now)],
            )
            if candidate is not None:
                self._insert(db, candidate, source=f"turn:{turn_id}")

    def select(self, query: TemporalQuery):
        now = datetime.now(UTC)
        as_of, known_at = utc(query.as_of) or now, utc(query.known_at) or now
        with self.connect() as db:
            db.execute("BEGIN")
            current = {
                row["id"]: dict(row) for row in db.execute("SELECT * FROM entries ORDER BY rowid")
            }
            owner_id = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
            entities = {item["id"]: item for item in records(db, "entities")}
            if query.known_at is None:
                chosen = current
            else:
                chosen = {}
                for row in db.execute("SELECT * FROM revisions ORDER BY id,revision DESC"):
                    if (
                        row["id"] not in chosen
                        and row["id"] in current
                        and utc(row["updated_at"]) <= known_at
                    ):
                        chosen[row["id"]] = dict(row)
        selected = []
        for raw in chosen.values():
            item = {field: raw[field] for field in _RECORD_COLUMNS.split(",")}
            if item["status"] != "confirmed" or item["owner_id"] != owner_id:
                continue
            if query.entity_id is not None and item["entity_id"] != query.entity_id:
                if item["entity_id"] is not None or item["kind"] != "preference":
                    continue
            entity = entities.get(item["entity_id"]) if item["entity_id"] else None
            current_entity = entities.get(current[item["id"]]["entity_id"])
            if item["entity_id"] and (
                not entity or entity["status"] != "confirmed" or entity["owner_id"] != owner_id
            ):
                continue
            sensitivity = max(
                (
                    item["sensitivity"],
                    current[item["id"]]["sensitivity"],
                    entity["sensitivity"] if entity else "public",
                    current_entity["sensitivity"] if current_entity else "public",
                ),
                key={"public": 0, "private": 1, "sensitive": 2}.__getitem__,
            )
            if sensitivity == "sensitive" and not query.allow_sensitive:
                continue
            belief = item["belief"]
            if not active_at(item, as_of):
                belief = (
                    "outdated"
                    if utc(item["valid_until"]) is not None and utc(item["valid_until"]) <= as_of
                    else "unknown"
                )
            if belief != "known" and not query.include_uncertain:
                continue
            selected.append(
                dict(
                    record=item,
                    effective_belief=belief,
                    effective_sensitivity=sensitivity,
                    historical=query.known_at is not None,
                )
            )
        return selected

    def context(
        self,
        question: str,
        *,
        allow_sensitive: bool = False,
        as_of=None,
        known_at=None,
        entity_id=None,
    ):
        if type(allow_sensitive) is not bool:
            raise MemoryInputError("Sensitive disclosure requires an explicit boolean")
        tokens = normalized_tokens(question)
        preferences: list[Match] = []
        facts: list[Match] = []
        items = self.select(
            TemporalQuery(
                allow_sensitive=allow_sensitive, as_of=as_of, known_at=known_at, entity_id=entity_id
            )
        )
        for selected in items:
            item = selected["record"]
            excerpt = f"{item['key']}: {item['content']}"
            overlap = len(tokens & normalized_tokens(excerpt)) / max(len(tokens), 1)
            # Preferences are always eligible, but do not outrank relevant factual evidence.
            if overlap or item["kind"] == "preference":
                doc = Document(title=item["key"], path=f"memory/{item['id']}", text=excerpt)
                match = Match(document=doc, excerpt=excerpt, score=overlap)
                (preferences if item["kind"] == "preference" else facts).append(match)
        # Preferences get a reserved floor of the budget so a flood of matching facts
        # cannot evict a confirmed preference; facts then fill the rest, and any budget
        # facts don't use goes back to preferences. Only once confirmed preferences and
        # relevant facts together exceed the total budget do the lowest-scoring
        # preferences beyond the reserved floor get dropped.
        preferences.sort(key=lambda m: m.score, reverse=True)
        facts.sort(key=lambda m: m.score, reverse=True)
        reserved = min(len(preferences), _MAX_PREFERENCE_MATCHES)
        kept_facts = facts[: _MAX_MATCHES - reserved]
        kept_preferences = preferences[: _MAX_MATCHES - len(kept_facts)]
        return sorted(kept_preferences + kept_facts, key=lambda m: m.score, reverse=True)
