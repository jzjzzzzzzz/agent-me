"""Local memory lifecycle and retrieval, usable without an HTTP server or model provider."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .knowledge import Document, Match
from .text import normalized_tokens

_SCHEMA_VERSION = 2
_MAX_MATCHES = 20
_MAX_PREFERENCE_MATCHES = 5
_RECORD_COLUMNS = "id,kind,key,content,source,status,created_at,updated_at,revision,superseded_by"


class MemoryError(Exception):
    """Domain failure; transports decide how to expose it to their callers."""


class MemoryNotFound(MemoryError):
    pass


class MemoryConflict(MemoryError):
    def __init__(self, message: str, *, conflicts: dict[str, int] | None = None):
        super().__init__(message)
        self.conflicts = conflicts


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kind: Literal["fact", "preference", "event", "decision"] = "fact"
    key: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=2000)


class MemoryRecord(Entry):
    """Owner-reviewed memory with server-controlled provenance and lifecycle fields."""

    id: str
    source: str
    status: Literal["pending", "confirmed", "superseded"]
    created_at: datetime
    updated_at: datetime
    revision: int = Field(ge=1)
    superseded_by: str | None


class MemoryRevision(MemoryRecord):
    change: Literal["baseline", "created", "edited", "confirmed", "superseded"]


class StoredTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class MemoryExport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[2] = 2
    entries: list[MemoryRecord]
    history: list[StoredTurn]
    revisions: list[MemoryRevision]


class EditEntry(Entry):
    expected_revision: int | None = Field(default=None, ge=1, strict=True)


class RestoreMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1, strict=True)
    expected_revision: int | None = Field(default=None, ge=1, strict=True)


class MemoryMutation(BaseModel):
    status: Literal["pending", "confirmed"]
    revision: int = Field(ge=1)


class Confirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int | None = Field(default=None, ge=1, strict=True)
    replace_ids: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=100
    )
    replace_revisions: (
        dict[
            Annotated[str, Field(min_length=1, max_length=100)],
            Annotated[int, Field(ge=1, strict=True)],
        ]
        | None
    ) = Field(default=None, max_length=100)

    @field_validator("replace_ids")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any(not item.strip() for item in value):
            raise ValueError("Replacement IDs must be nonblank and unique")
        return value


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
                revision INTEGER NOT NULL DEFAULT 1, superseded_by TEXT
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
        db.execute("""
            CREATE TABLE IF NOT EXISTS revisions (
                id TEXT NOT NULL, kind TEXT NOT NULL, key TEXT NOT NULL,
                content TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                revision INTEGER NOT NULL, superseded_by TEXT, change TEXT NOT NULL,
                PRIMARY KEY (id, revision)
            )
        """)
        columns = ",".join(f"e.{column}" for column in _RECORD_COLUMNS.split(","))
        db.execute(f"""
            INSERT INTO revisions ({_RECORD_COLUMNS},change)
            SELECT {columns}, 'baseline' FROM entries e
            WHERE NOT EXISTS (SELECT 1 FROM revisions r WHERE r.id=e.id)
        """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
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

    def export(self):
        # An explicit read transaction pins all tables to the same SQLite snapshot.
        with self.connect() as db:
            db.execute("BEGIN")
            entries = [dict(r) for r in db.execute("SELECT * FROM entries ORDER BY rowid")]
            turns = [dict(r) for r in db.execute("SELECT * FROM turns ORDER BY rowid")]
            revisions = [dict(r) for r in db.execute("SELECT * FROM revisions ORDER BY rowid")]
        return {"version": 2, "entries": entries, "history": turns, "revisions": revisions}

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
        )
        db.execute(
            f"INSERT INTO entries ({_RECORD_COLUMNS}) VALUES "
            "(:id,:kind,:key,:content,:source,:status,"
            ":created_at,:updated_at,:revision,:superseded_by)",
            item,
        )
        self._snapshot(db, item["id"], "created")
        return item

    def add(self, entry: Entry, source: str = "manual"):
        with self.connect() as db:
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
            entry = Entry(kind=item["kind"], key=item["key"], content=item["content"])
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
            db.execute(
                "UPDATE entries SET kind=?,key=?,content=?,source='manual',status='pending',"
                "updated_at=?,revision=revision+1 "
                "WHERE id=?",
                (entry.kind, entry.key, entry.content, datetime.now(UTC).isoformat(), entry_id),
            )
            self._snapshot(db, entry_id, "edited")
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
            conflict_revisions = {
                r["id"]: r["revision"]
                for r in db.execute(
                    "SELECT id,revision FROM entries WHERE kind=? AND key=? "
                    "AND status='confirmed' AND id!=?",
                    (item["kind"], item["key"], entry_id),
                )
            }
            conflicts = list(conflict_revisions)
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
            db.execute("DELETE FROM revisions WHERE id=?", (entry_id,))
            db.execute("DELETE FROM entries WHERE id=?", (entry_id,))
        return {"deleted": True}

    def history(self):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM turns ORDER BY rowid DESC LIMIT 100").fetchall()
            return [dict(r) for r in reversed(rows)]

    def clear_history(self):
        with self.connect() as db:
            db.execute("DELETE FROM turns")
        return {"deleted": True}

    def save_chat(self, question: str, answer: str):
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
            now = datetime.now(UTC).isoformat()
            db.executemany(
                "INSERT INTO turns VALUES (?,?,?,?)",
                [(turn_id, "user", question, now), (uuid4().hex, "assistant", answer, now)],
            )
            if candidate is not None:
                self._insert(db, candidate, source=f"turn:{turn_id}")

    def context(self, question: str):
        tokens = normalized_tokens(question)
        preferences: list[Match] = []
        facts: list[Match] = []
        with self.connect() as db:
            items = db.execute(
                "SELECT * FROM entries WHERE status='confirmed' ORDER BY rowid"
            ).fetchall()
        for item in items:
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
