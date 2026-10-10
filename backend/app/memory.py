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

from .knowledge import Document, Match
from .memory_models import Confirm, EditEntry, Entry, RestoreMemory
from .text import normalized_tokens

_SCHEMA_VERSION = 3
_MAX_MATCHES = 20
_MAX_PREFERENCE_MATCHES = 5
_RECORD_COLUMNS = (
    "id,kind,key,content,source,status,created_at,updated_at,revision,superseded_by,sensitivity"
)


def memory_digest(kind: str, key: str, content: str) -> str:
    """Exact normalized identity, not a semantic-equivalence or truth judgement."""
    values = [
        unicodedata.normalize("NFC", value.strip().replace("\r\n", "\n"))
        for value in (kind, key, content)
    ]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode("utf-8")).hexdigest()


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
            [
                (row["id"], memory_digest(row["kind"], row["key"], row["content"]))
                for row in db.execute("SELECT * FROM entries")
            ],
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
        return {
            "version": 3,
            "entries": entries,
            "history": turns,
            "revisions": revisions,
            "sources": sources,
            "ingestion_runs": runs,
            "origins": origins,
            "forgotten": forgotten,
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
            sensitivity=entry.sensitivity,
        )
        db.execute(
            f"INSERT INTO entries ({_RECORD_COLUMNS}) VALUES "
            "(:id,:kind,:key,:content,:source,:status,"
            ":created_at,:updated_at,:revision,:superseded_by,:sensitivity)",
            item,
        )
        self._snapshot(db, item["id"], "created")
        db.execute(
            "INSERT INTO memory_digests VALUES (?,?)",
            (item["id"], memory_digest(item["kind"], item["key"], item["content"])),
        )
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
            entry = Entry(
                kind=item["kind"],
                key=item["key"],
                content=item["content"],
                sensitivity=max(
                    (current["sensitivity"], item["sensitivity"]),
                    key={"public": 0, "private": 1, "sensitive": 2}.__getitem__,
                ),
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
            db.execute(
                "UPDATE entries SET kind=?,key=?,content=?,source='manual',status='pending',"
                "updated_at=?,revision=revision+1,sensitivity=? "
                "WHERE id=?",
                (
                    entry.kind,
                    entry.key,
                    entry.content,
                    datetime.now(UTC).isoformat(),
                    entry.sensitivity
                    if "sensitivity" in entry.model_fields_set
                    else item["sensitivity"],
                    entry_id,
                ),
            )
            self._snapshot(db, entry_id, "edited")
            db.execute(
                "UPDATE memory_digests SET digest=? WHERE memory_id=?",
                (memory_digest(entry.kind, entry.key, entry.content), entry_id),
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
            conflict_revisions = {
                r["id"]: r["revision"]
                for r in db.execute(
                    "SELECT id,revision FROM entries WHERE kind=? AND key=? COLLATE NFC "
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
            db.execute("BEGIN IMMEDIATE")
            for row in db.execute("SELECT * FROM revisions WHERE id=?", (entry_id,)).fetchall():
                db.execute(
                    "INSERT OR REPLACE INTO forgotten VALUES (?,?)",
                    (
                        memory_digest(row["kind"], row["key"], row["content"]),
                        datetime.now(UTC).isoformat(),
                    ),
                )
            db.execute("DELETE FROM origins WHERE memory_id=?", (entry_id,))
            db.execute("DELETE FROM memory_digests WHERE memory_id=?", (entry_id,))
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

    def context(self, question: str, *, allow_sensitive: bool = False):
        if type(allow_sensitive) is not bool:
            raise MemoryInputError("Sensitive disclosure requires an explicit boolean")
        tokens = normalized_tokens(question)
        preferences: list[Match] = []
        facts: list[Match] = []
        with self.connect() as db:
            items = db.execute(
                "SELECT * FROM entries WHERE status='confirmed' ORDER BY rowid"
            ).fetchall()
        for item in items:
            if item["sensitivity"] == "sensitive" and not allow_sensitive:
                continue
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
