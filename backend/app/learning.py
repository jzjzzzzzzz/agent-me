"""Approved-source ingestion with exact excerpts, review, replay and forgetting boundaries."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from .audit import AuditLog
from .audit import record as audit_record
from .learning_policy import matches_prefix
from .learning_policy import settings as learning_settings
from .memory import (
    MemoryConflict,
    MemoryInputError,
    MemoryNotFound,
    MemoryPermissionDenied,
    Store,
    memory_digest,
    record_digest,
)
from .memory_models import Entry, IngestionInput, SourceInput
from .memory_time import iso

EXTRACTOR = "exact-excerpts-v1"
MAX_DOCUMENT_BYTES = 200_000
MAX_CANDIDATES = 100
_LEVEL = {"public": 0, "private": 1, "sensitive": 2}
_FIELD = re.compile(
    r"^\s*(?:[-*]\s+)?(?P<kind>fact|preference|event|decision)\s+"
    r"(?P<key>[^\s:]{1,100})\s*:\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Candidate:
    entry: Entry
    start: int
    end: int
    excerpt: str


def _slug(text: str) -> str:
    return re.sub(r"[^\w.-]+", ".", text.casefold()).strip(".")[:64] or "untitled"


def extract(content: str, source: dict, mode: str, temporal=None) -> list[Candidate]:
    """Propose literal source data, never infer identity or execute source instructions."""
    candidates: list[Candidate] = []

    def append(kind: str, key: str, start: int, end: int):
        try:
            entry = Entry(
                kind=kind,
                key=key,
                content=content[start:end],
                sensitivity=source["sensitivity"],
                entity_id=source.get("entity_id"),
                valid_from=(temporal or {}).get("valid_from"),
                valid_until=(temporal or {}).get("valid_until"),
                occurred_at=(temporal or {}).get("occurred_at")
                if kind in {"event", "decision"}
                else None,
            )
        except ValidationError:
            raise MemoryInputError("Extracted record exceeds the memory contract") from None
        candidates.append(Candidate(entry, start, end, content[start:end]))
        if len(candidates) > MAX_CANDIDATES:
            raise MemoryInputError("Document exceeds the candidate limit")

    if mode == "fields":
        offset = 0
        for line in content.splitlines(keepends=True):
            stripped = line.strip()
            if stripped and not stripped.startswith(("#", "```")):
                match = _FIELD.match(line)
                if not match:
                    raise MemoryInputError("Fields mode requires 'kind key: content' lines")
                start = offset + match.start("value")
                end = offset + match.end("value")
                append(match["kind"].lower(), match["key"], start, end)
            offset += len(line)
    else:
        # Whole paragraphs remain quotations, not model-inferred personal claims.
        kind = "event" if source["kind"] in {"event", "conversation"} else "fact"
        section = "notes"
        ordinal = 0
        start: int | None = None
        end = offset = 0

        def flush():
            nonlocal start, ordinal
            if start is not None:
                key = f"notes.{_slug(source['name'])[:24]}.{section[:40]}.{ordinal}"
                append(kind, key, start, end)
                ordinal += 1
                start = None

        for line in content.splitlines(keepends=True):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                flush()
                if stripped.startswith("#"):
                    section = _slug(stripped.lstrip("#").strip())
                    ordinal = 0
            else:
                if start is None:
                    start = offset + len(line) - len(line.lstrip())
                end = offset + len(line.rstrip())
            offset += len(line)
        flush()
    if not candidates:
        raise MemoryInputError("Document contains no candidate records")
    return candidates


class LearningPipeline:
    def __init__(self, store: Store):
        self.store = store

    def sources(self):
        with self.store.connect() as db:
            return [
                {**dict(row), "approved": bool(row["approved"])}
                for row in db.execute("SELECT * FROM sources ORDER BY rowid")
            ]

    def register(self, payload: SourceInput):
        from .identity import IdentityStore

        entity_id = payload.entity_id
        if payload.entity_alias is not None:
            result = IdentityStore(self.store).resolve(payload.entity_alias, allow_sensitive=True)
            if result["status"] != "resolved":
                raise MemoryConflict("Source identity alias is unknown or ambiguous")
            entity_id = result["matches"][0]["id"]
        now = datetime.now(UTC).isoformat()
        item = dict(
            id=uuid4().hex,
            **payload.model_dump(exclude={"entity_alias", "entity_id"}),
            entity_id=entity_id,
            owner_id=self.store.owner_id,
            approved=False,
            revision=1,
            created_at=now,
            updated_at=now,
        )
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.store._entity(db, entity_id)
            db.execute(
                "INSERT INTO sources (id,kind,name,sensitivity,approved,revision,created_at,"
                "updated_at,entity_id,owner_id) VALUES "
                "(:id,:kind,:name,:sensitivity,:approved,:revision,"
                ":created_at,:updated_at,:entity_id,:owner_id)",
                item,
            )
            audit_record(db, "learning.source_register", counts={"sources": 1})
        return item

    def approve(
        self, source_id: str, *, approved: bool = True, expected_revision: int | None = None
    ):
        if type(approved) is not bool or (
            expected_revision is not None
            and (type(expected_revision) is not int or expected_revision < 1)
        ):
            raise MemoryInputError("Invalid source review precondition")
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            source = db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
            if not source:
                raise MemoryNotFound("Source not found")
            if expected_revision is not None and source["revision"] != expected_revision:
                raise MemoryConflict("Source changed; refresh before reviewing")
            if bool(source["approved"]) != approved:
                db.execute(
                    "UPDATE sources SET approved=?,revision=revision+1,updated_at=? WHERE id=?",
                    (approved, datetime.now(UTC).isoformat(), source_id),
                )
            item = dict(db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone())
            audit_record(db, "learning.source_approve" if approved else "learning.source_revoke")
            return {**item, "approved": bool(item["approved"])}

    def origins(self, memory_id: str):
        with self.store.connect() as db:
            db.execute("BEGIN")
            if not db.execute("SELECT 1 FROM entries WHERE id=?", (memory_id,)).fetchone():
                raise MemoryNotFound("Memory not found")
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM origins WHERE memory_id=? ORDER BY rowid", (memory_id,)
                )
            ]

    def runs(self):
        with self.store.connect() as db:
            rows = db.execute("SELECT run_json FROM ingestion_runs ORDER BY rowid DESC LIMIT 100")
            return [json.loads(row[0]) for row in rows]

    def _source(self, db, source_id, expected_revision):
        source = db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
        if not source:
            raise MemoryNotFound("Source not found")
        if not source["approved"]:
            raise MemoryPermissionDenied("Source is not approved for learning")
        if expected_revision is not None and source["revision"] != expected_revision:
            raise MemoryConflict("Source changed; refresh before ingesting")
        item = dict(source)
        entity = self.store._entity(db, item["entity_id"])
        if entity:
            item["sensitivity"] = max(
                (item["sensitivity"], entity["sensitivity"]), key=_LEVEL.__getitem__
            )
        policy = learning_settings(db)["policy"]
        if (
            item["kind"] not in policy["source_kinds"]
            or item["sensitivity"] not in policy["labels"]
        ):
            raise MemoryPermissionDenied("Source is outside the owner's learning policy")
        return item

    @staticmethod
    def _save(db, replay_key, run):
        db.execute(
            "INSERT INTO ingestion_runs VALUES (?,?,?) ON CONFLICT(replay_key) "
            "DO UPDATE SET run_json=excluded.run_json",
            (run["id"], replay_key, json.dumps(run, ensure_ascii=False)),
        )
        audit_record(
            db,
            "learning.ingest",
            "succeeded" if run["status"] == "completed" else "failed",
            counts={"items": len(run["items"]), "attempts": run["attempts"]},
        )

    def ingest(self, source_id: str, payload: IngestionInput):
        if len(payload.content.encode("utf-8")) > MAX_DOCUMENT_BYTES:
            raise MemoryInputError("Document exceeds the ingestion byte limit")
        digest = hashlib.sha256(payload.content.encode("utf-8")).hexdigest()
        run = None
        replay_key = ""
        try:
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                source = self._source(db, source_id, payload.expected_source_revision)
                identity = [
                    source_id,
                    source["revision"],
                    digest,
                    payload.mode,
                    EXTRACTOR,
                ]
                qualifier = [
                    iso(payload.valid_from),
                    iso(payload.valid_until),
                    iso(payload.occurred_at),
                ]
                if any(value is not None for value in qualifier):
                    identity.append(qualifier)
                replay_key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
                previous = db.execute(
                    "SELECT run_json FROM ingestion_runs WHERE replay_key=?", (replay_key,)
                ).fetchone()
                previous = json.loads(previous[0]) if previous else None
                if previous and previous["status"] == "completed":
                    audit_record(db, "learning.replay")
                    return {**previous, "replayed": True}
                now = datetime.now(UTC).isoformat()
                run = dict(
                    id=previous["id"] if previous else uuid4().hex,
                    source_id=source_id,
                    source_revision=source["revision"],
                    document_hash=digest,
                    extractor=EXTRACTOR,
                    mode=payload.mode,
                    status="completed",
                    attempts=previous["attempts"] + 1 if previous else 1,
                    created_at=previous["created_at"] if previous else now,
                    updated_at=now,
                    replayed=False,
                    error_code=None,
                    items=[],
                    trace=[dict(stage="source", outcome="completed", count=1)],
                )
                try:
                    candidates = extract(
                        payload.content,
                        source,
                        payload.mode,
                        temporal={
                            field: getattr(payload, field)
                            for field in ("valid_from", "valid_until", "occurred_at")
                        },
                    )
                    policy = learning_settings(db)["policy"]
                    if len(candidates) > policy["max_candidates"] or any(
                        matches_prefix(candidate.entry.key, policy["blocked_key_prefixes"])
                        for candidate in candidates
                    ):
                        raise MemoryInputError("Candidates are outside the owner's learning policy")
                except MemoryInputError:
                    run.update(status="failed", error_code="extraction_invalid")
                    run["trace"].append(dict(stage="extraction", outcome="failed", count=0))
                    self._save(db, replay_key, run)
                    return run
                run["trace"].append(
                    dict(stage="extraction", outcome="completed", count=len(candidates))
                )
                self._apply(db, source, candidates, run)
                self._save(db, replay_key, run)
                return run
        except (MemoryConflict, MemoryNotFound, MemoryPermissionDenied):
            AuditLog(self.store).record("learning.ingest", "denied")
            raise
        except Exception:
            if run is None:
                raise
            # Candidate/origin writes have rolled back. Record a content-free failure,
            # without overwriting a concurrent successful retry of the same input.
            run.update(status="failed", error_code="storage_failed", items=[])
            run["trace"] = [stage for stage in run["trace"] if stage["stage"] != "storage"]
            run["trace"].append(dict(stage="storage", outcome="failed", count=0))
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                # Revoking learning permission does not revoke the owner's ability to
                # inspect an earlier authorized attempt's content-free failure trace.
                previous = db.execute(
                    "SELECT run_json FROM ingestion_runs WHERE replay_key=?", (replay_key,)
                ).fetchone()
                if previous and json.loads(previous[0])["status"] == "completed":
                    audit_record(db, "learning.replay")
                    return {**json.loads(previous[0]), "replayed": True}
                if previous:
                    saved = json.loads(previous[0])
                    run["id"] = saved["id"]
                    run["created_at"] = saved["created_at"]
                    run["attempts"] = max(run["attempts"], saved["attempts"] + 1)
                self._save(db, replay_key, run)
            return run

    def _apply(self, db, source, candidates, run):
        created = duplicated = conflicts = 0
        for index, candidate in enumerate(candidates):
            entry = candidate.entry
            digest = record_digest(entry.model_dump(mode="json"))
            # Legacy unscoped forgetting remains conservative when a caller later binds identity.
            legacy = memory_digest(entry.kind, entry.key, entry.content)
            if db.execute(
                "SELECT 1 FROM forgotten WHERE digest IN (?,?)", (digest, legacy)
            ).fetchone():
                run["items"].append(
                    dict(index=index, outcome="forgotten", memory_id=None, conflict_ids=[])
                )
                continue
            same = db.execute(
                "SELECT e.* FROM entries e JOIN memory_digests d ON d.memory_id=e.id "
                "WHERE d.digest=? AND e.status!='superseded' "
                "ORDER BY (e.status='confirmed') DESC,e.rowid LIMIT 1",
                (digest,),
            ).fetchone()
            if same and same["status"] == "confirmed":
                duplicated += 1
                run["items"].append(
                    dict(index=index, outcome="known", memory_id=same["id"], conflict_ids=[])
                )
                continue
            if same:
                duplicated += 1
                item = dict(same)
                outcome = "duplicate"
                origin = db.execute(
                    "SELECT 1 FROM origins WHERE memory_id=? AND source_id=? AND document_hash=? "
                    "AND start=? AND end=?",
                    (
                        item["id"],
                        source["id"],
                        run["document_hash"],
                        candidate.start,
                        candidate.end,
                    ),
                ).fetchone()
                if not origin:
                    sensitivity = max(
                        [item["sensitivity"], entry.sensitivity], key=_LEVEL.__getitem__
                    )
                    db.execute(
                        "UPDATE entries SET revision=revision+1,sensitivity=?,updated_at=? "
                        "WHERE id=?",
                        (sensitivity, run["updated_at"], item["id"]),
                    )
                    self.store._snapshot(db, item["id"], "corroborated")
                    item["revision"] += 1
            else:
                created += 1
                outcome = "created"
                item = self.store._insert(db, entry, source=f"source:{source['id']}")
            conflict_ids = list(self.store._conflicts(db, item))
            conflicts += bool(conflict_ids)
            db.execute(
                "INSERT OR IGNORE INTO origins VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    uuid4().hex,
                    item["id"],
                    item["revision"],
                    source["id"],
                    source["revision"],
                    run["document_hash"],
                    candidate.start,
                    candidate.end,
                    candidate.excerpt,
                    run["id"],
                    run["updated_at"],
                ),
            )
            run["items"].append(
                dict(index=index, outcome=outcome, memory_id=item["id"], conflict_ids=conflict_ids)
            )
        run["trace"].extend(
            [
                dict(stage="deduplication", outcome="completed", count=duplicated),
                dict(stage="conflicts", outcome="completed", count=conflicts),
                dict(stage="storage", outcome="completed", count=created),
            ]
        )
