"""Version-four identity/temporal schema extension, called inside one migration transaction."""

import json
from uuid import uuid4


def extend_records(db):
    db.execute("CREATE TABLE IF NOT EXISTS workspace (key TEXT PRIMARY KEY,value TEXT NOT NULL)")
    db.execute("INSERT OR IGNORE INTO workspace VALUES ('owner_id',?)", (uuid4().hex,))
    db.execute("INSERT OR IGNORE INTO workspace VALUES ('retention_policy','{}')")
    db.execute("INSERT OR IGNORE INTO workspace VALUES ('retention_revision','1')")
    owner = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
    fields = {
        "entity_id": "TEXT",
        "confidence": "REAL",
        "belief": "TEXT NOT NULL DEFAULT 'known'",
        "valid_from": "TEXT",
        "valid_until": "TEXT",
        "occurred_at": "TEXT",
        "owner_id": "TEXT NOT NULL DEFAULT ''",
        "category": "TEXT NOT NULL DEFAULT 'semantic'",
    }
    for table in ("entries", "revisions"):
        existing = {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}
        for field, definition in fields.items():
            if field not in existing:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {field} {definition}")
        db.execute(f"UPDATE {table} SET owner_id=? WHERE owner_id=''", (owner,))
        db.execute(
            f"UPDATE {table} SET category=CASE WHEN kind='preference' THEN 'preference' "
            "WHEN kind IN ('event','decision') THEN 'episodic' ELSE 'semantic' END"
        )


def extend_identity(db):
    columns = {r["name"] for r in db.execute("PRAGMA table_info(sources)")}
    if "entity_id" not in columns:
        db.execute("ALTER TABLE sources ADD COLUMN entity_id TEXT")
    if "owner_id" not in columns:
        db.execute("ALTER TABLE sources ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''")
    owner = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
    db.execute("UPDATE sources SET owner_id=? WHERE owner_id=''", (owner,))
    for table in ("entities", "relationships"):
        db.execute(
            f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, data_json TEXT NOT NULL)"
        )
        db.execute(
            f"CREATE TABLE IF NOT EXISTS {table}_revisions "
            "(id TEXT NOT NULL,revision INTEGER NOT NULL,data_json TEXT NOT NULL,"
            "PRIMARY KEY(id,revision))"
        )
    db.execute(
        "CREATE TABLE IF NOT EXISTS retention_plans (id TEXT PRIMARY KEY,data_json TEXT NOT NULL)"
    )


def records(db, table):
    return [
        json.loads(row[0]) for row in db.execute(f"SELECT data_json FROM {table} ORDER BY rowid")
    ]
