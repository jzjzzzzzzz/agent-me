"""Digest-reviewed, transactional portable import into an empty local workspace.

Data and history move; executable approvals/permissions do not. Archives are inert data.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from .audit import record
from .memory import MemoryConflict, MemoryInputError, Store, record_digest
from .memory_models import MemoryExport
from .owner_models import ImportArchive, ImportPreview, ImportResult

MAX_IMPORT_BYTES = 16 * 1024 * 1024
MAX_COLLECTION = 10000
MAX_TOTAL_RECORDS = 50000
DATA_TABLES = (
    "entries",
    "revisions",
    "turns",
    "sources",
    "ingestion_runs",
    "origins",
    "forgotten",
    "entities",
    "entities_revisions",
    "relationships",
    "relationships_revisions",
    "retention_plans",
    "tool_permissions",
    "action_plans",
    "tasks",
    "notes",
    "action_events",
    "consolidation_plans",
    "import_archives",
)
OWNED = (
    "entries",
    "revisions",
    "sources",
    "entities",
    "entity_revisions",
    "relationships",
    "relationship_revisions",
    "retention_plans",
    "tool_permissions",
    "action_plans",
    "tasks",
    "notes",
    "consolidation_plans",
    "audit_events",
    "import_archives",
)


def encoded(value):
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode(
            "utf-8"
        )
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise MemoryInputError("Snapshot must contain bounded valid JSON/Unicode") from None


def unique(items, fields=("id",)):
    keys = [tuple(item[field] for field in fields) for item in items]
    if len(keys) != len(set(keys)) or any(
        isinstance(value, str) and (not value.strip() or len(value) > 100)
        for key in keys
        for value in key
    ):
        raise MemoryInputError("Snapshot IDs/revisions must be bounded, nonblank and unique")


def histories(current, history):
    unique(current)
    unique(history, ("id", "revision"))
    current_by_id = {item["id"]: item for item in current}
    latest = {}
    for item in sorted(history, key=lambda row: row["revision"]):
        if item["id"] not in current_by_id:
            raise MemoryInputError("Snapshot history has no current record")
        if item["id"] in latest and datetime.fromisoformat(
            item["updated_at"]
        ) < datetime.fromisoformat(latest[item["id"]]["updated_at"]):
            raise MemoryInputError("Snapshot history times must be monotonic")
        latest[item["id"]] = {key: value for key, value in item.items() if key != "change"}
    if latest != current_by_id:
        raise MemoryInputError("Snapshot latest revisions must exactly match current records")


def validate_integrity(data):
    owner = data["owner_id"]
    if not owner.strip() or len(owner) > 100:
        raise MemoryInputError("Invalid snapshot owner")
    for name in OWNED:
        if any(item["owner_id"] != owner for item in data[name]):
            raise MemoryInputError("Snapshot mixes workspace owners")
    for name, items in data.items():
        if isinstance(items, list):
            for item in items:
                for key in ("created_at", "updated_at", "forgotten_at"):
                    if key in item:
                        at = datetime.fromisoformat(item[key])
                        if at.utcoffset() is None:
                            raise MemoryInputError(
                                "Snapshot timestamps must have explicit timezones"
                            )
                if "updated_at" in item and datetime.fromisoformat(
                    item["updated_at"]
                ) < datetime.fromisoformat(item["created_at"]):
                    raise MemoryInputError("Snapshot update predates record creation")
            if items and "id" in items[0]:
                unique(
                    items,
                    ("id", "revision")
                    if name in {"revisions", "entity_revisions", "relationship_revisions"}
                    else ("id",),
                )
    histories(data["entries"], data["revisions"])
    histories(data["entities"], data["entity_revisions"])
    histories(data["relationships"], data["relationship_revisions"])
    entities = {item["id"]: item for item in data["entities"]}
    sources = {item["id"]: item for item in data["sources"]}
    memory = {(item["id"], item["revision"]): item for item in data["revisions"]}
    for item in [*data["entries"], *data["revisions"], *data["sources"]]:
        if item.get("entity_id") and item["entity_id"] not in entities:
            raise MemoryInputError("Snapshot has unresolved memory/source subjects")
        if "category" in item:
            category = (
                "episodic"
                if item["kind"] in {"event", "decision"}
                else "preference"
                if item["kind"] == "preference"
                else "semantic"
            )
            if item["category"] != category:
                raise MemoryInputError("Snapshot memory category disagrees with its kind")
    if data["owner_entity_id"] is not None:
        person = entities.get(data["owner_entity_id"])
        if not person or person["kind"] != "person":
            raise MemoryInputError("Snapshot owner binding must name a person")
    for item in [*data["relationships"], *data["relationship_revisions"]]:
        if (
            item["from_entity_id"] not in entities
            or item["to_entity_id"] not in entities
            or (item["evidence_id"], item["evidence_revision"]) not in memory
        ):
            raise MemoryInputError("Snapshot relationship provenance is unresolved")
    for origin in data["origins"]:
        revision = memory.get((origin["memory_id"], origin["memory_revision"]))
        source = sources.get(origin["source_id"])
        if not revision or not source or source["revision"] < origin["source_revision"]:
            raise MemoryInputError("Snapshot origin provenance is unresolved")
        if origin["end"] - origin["start"] != len(origin["excerpt"]) or unicodedata.normalize(
            "NFC", origin["excerpt"].strip().replace("\r\n", "\n")
        ) != unicodedata.normalize("NFC", revision["content"].replace("\r\n", "\n")):
            raise MemoryInputError("Snapshot origin does not match its literal memory revision")
    unique(data["origins"], ("memory_id", "source_id", "document_hash", "start", "end"))
    if any(item.get("entity_alias") is not None for item in data["sources"]):
        raise MemoryInputError("Registered snapshot sources must use resolved entity IDs")
    for run in data["ingestion_runs"]:
        if run["source_id"] not in sources:
            raise MemoryInputError("Snapshot ingestion source is unresolved")
    unique(data["ingestion_replay_keys"], ("run_id",))
    if {item["run_id"] for item in data["ingestion_replay_keys"]} != {
        item["id"] for item in data["ingestion_runs"]
    } or len({item["key"] for item in data["ingestion_replay_keys"]}) != len(
        data["ingestion_replay_keys"]
    ):
        raise MemoryInputError("Snapshot replay keys must exactly cover ingestion runs")
    unique(data["forgotten"], ("digest",))
    if any(
        len(item["digest"]) != 64 or any(c not in "0123456789abcdef" for c in item["digest"])
        for item in data["forgotten"]
    ):
        raise MemoryInputError("Snapshot forgetting digests must be SHA-256 values")
    unique(data["tool_permissions"], ("tool",))


class PortableMemory:
    def __init__(self, store: Store):
        self.store = store

    @staticmethod
    def _snapshot(payload):
        if (
            not isinstance(payload, dict)
            or type(payload.get("version")) is not int
            or payload["version"] not in {6, 7}
        ):
            raise MemoryInputError("Supported portable snapshot versions are 6 and 7")
        if len(encoded(payload)) > MAX_IMPORT_BYTES:
            raise MemoryInputError("Snapshot exceeds the 16 MiB import limit")
        version = payload["version"]
        raw = dict(payload)
        if version == 6:
            if any(
                key in raw for key in ("audit_events", "import_archives", "ingestion_replay_keys")
            ):
                raise MemoryInputError("Version 6 snapshot cannot contain version 7 extensions")
            legacy_runs = raw.get("ingestion_runs", [])
            if not isinstance(legacy_runs, list) or any(
                not isinstance(item, dict) or not isinstance(item.get("id"), str)
                for item in legacy_runs
            ):
                raise MemoryInputError("Snapshot violates the portable schema")
            raw.update(
                version=7,
                audit_events=[],
                import_archives=[],
                ingestion_replay_keys=[
                    {
                        "run_id": item["id"],
                        "key": hashlib.sha256(("legacy-import:" + item["id"]).encode()).hexdigest(),
                    }
                    for item in legacy_runs
                ],
            )
        lists = [value for value in raw.values() if isinstance(value, list)]
        if (
            any(len(value) > MAX_COLLECTION for value in lists)
            or sum(map(len, lists)) > MAX_TOTAL_RECORDS
        ):
            raise MemoryInputError("Snapshot exceeds bounded record counts")
        try:
            data = MemoryExport.model_validate(raw).model_dump(mode="json")
        except ValidationError:
            raise MemoryInputError("Snapshot violates the portable schema") from None
        validate_integrity(data)
        digest = hashlib.sha256(encoded({"source_version": version, "snapshot": data})).hexdigest()
        return data, version, digest

    @staticmethod
    def _empty(db):
        if any(
            db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
            for table in (*DATA_TABLES, "memory_digests")
        ):
            raise MemoryConflict("Portable import requires an empty destination workspace")
        for key, value in db.execute("SELECT key,value FROM workspace"):
            if (
                key
                not in {
                    "owner_id",
                    "retention_policy",
                    "retention_revision",
                    "learning_policy",
                    "learning_revision",
                }
                or key.endswith("_revision")
                and value != "1"
                or key.endswith("_policy")
                and json.loads(value) != {}
            ):
                raise MemoryConflict("Portable import cannot overwrite configured owner state")

    def preview(self, payload):
        data, version, digest = self._snapshot(payload)
        with self.store.connect() as db:
            db.execute("BEGIN")
            self._empty(db)
        return ImportPreview(
            digest=digest,
            source_version=version,
            owner_id=data["owner_id"],
            counts={key: len(value) for key, value in data.items() if isinstance(value, list)},
        ).model_dump(mode="json")

    @staticmethod
    def _rows(db, table, items):
        columns = [row["name"] for row in db.execute(f"PRAGMA table_info({table})")]
        for item in items:
            db.execute(
                f"INSERT INTO {table} ({','.join(columns)}) "
                f"VALUES ({','.join('?' for _ in columns)})",
                [item[column] for column in columns],
            )

    def _write(self, db, data, version, digest):
        # Empty destination has only initializer/access audit; adopt the imported owner.
        db.execute("DELETE FROM audit_events")
        db.execute("UPDATE workspace SET value=? WHERE key='owner_id'", (data["owner_id"],))
        if data["owner_entity_id"]:
            db.execute(
                "INSERT INTO workspace VALUES ('owner_entity_id',?)", (data["owner_entity_id"],)
            )
        for field, key in [("retention_policy", "retention"), ("learning_policy", "learning")]:
            settings = data[field]
            db.execute(
                "UPDATE workspace SET value=? WHERE key=?",
                (json.dumps(settings["policy"]), key + "_policy"),
            )
            db.execute(
                "UPDATE workspace SET value=? WHERE key=?",
                (str(settings["revision"]), key + "_revision"),
            )
        for field, table in [
            ("entries", "entries"),
            ("revisions", "revisions"),
            ("history", "turns"),
            ("origins", "origins"),
            ("forgotten", "forgotten"),
        ]:
            self._rows(db, table, data[field])
        now = datetime.now(UTC)
        sources = [
            {
                **item,
                "approved": False,
                "revision": item["revision"] + 1,
                "updated_at": max(now, datetime.fromisoformat(item["updated_at"])).isoformat(),
            }
            for item in data["sources"]
        ]
        self._rows(db, "sources", sources)
        for field, table in [
            ("entities", "entities"),
            ("relationships", "relationships"),
            ("tasks", "tasks"),
            ("notes", "notes"),
            ("audit_events", "audit_events"),
            ("import_archives", "import_archives"),
        ]:
            for item in data[field]:
                db.execute(f"INSERT INTO {table} VALUES (?,?)", (item["id"], json.dumps(item)))
        for field, table in [
            ("entity_revisions", "entities_revisions"),
            ("relationship_revisions", "relationships_revisions"),
        ]:
            for item in data[field]:
                db.execute(
                    f"INSERT INTO {table} VALUES (?,?,?)",
                    (item["id"], item["revision"], json.dumps(item)),
                )
        replay = {item["run_id"]: item["key"] for item in data["ingestion_replay_keys"]}
        for run in data["ingestion_runs"]:
            db.execute(
                "INSERT INTO ingestion_runs VALUES (?,?,?)",
                (run["id"], replay[run["id"]], json.dumps(run)),
            )
        for item in data["entries"]:
            db.execute("INSERT INTO memory_digests VALUES (?,?)", (item["id"], record_digest(item)))
        archive = ImportArchive(
            id=uuid4().hex,
            owner_id=data["owner_id"],
            source_version=version,
            snapshot_digest=digest,
            created_at=datetime.now(UTC),
            authority={
                key: data[key]
                for key in [
                    "tool_permissions",
                    "action_plans",
                    "action_events",
                    "retention_plans",
                    "consolidation_plans",
                ]
            }
            | {"source_approvals": data["sources"]},
        )
        db.execute(
            "INSERT INTO import_archives VALUES (?,?)", (archive.id, archive.model_dump_json())
        )
        record(db, "portability.import", counts={"entries": len(data["entries"]), "archives": 1})
        return archive.id

    def apply(self, payload, reviewed_digest):
        data, version, digest = self._snapshot(payload)
        if digest != reviewed_digest:
            raise MemoryConflict("Import approval must match the exact reviewed snapshot")
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._empty(db)
            archive_id = self._write(db, data, version, digest)
        return ImportResult(
            digest=digest,
            source_version=version,
            owner_id=data["owner_id"],
            archive_id=archive_id,
            counts={key: len(value) for key, value in data.items() if isinstance(value, list)},
        ).model_dump(mode="json")
