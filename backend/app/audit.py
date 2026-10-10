"""Bounded operational audit with no questions, source text, paths, tokens or exception text."""

from datetime import UTC, datetime
from uuid import uuid4

from .owner_models import AuditEvent


def record(db, operation, outcome="succeeded", *, actor="core", counts=None):
    owner = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
    event = AuditEvent(
        id=uuid4().hex,
        owner_id=owner,
        actor=actor,
        operation=operation,
        outcome=outcome,
        counts=counts or {},
        created_at=datetime.now(UTC),
    )
    db.execute("INSERT INTO audit_events VALUES (?,?)", (event.id, event.model_dump_json()))
    # Bounded operational log, not an immutable/compliance log. Owners can export before rotation.
    db.execute(
        "DELETE FROM audit_events WHERE rowid NOT IN "
        "(SELECT rowid FROM audit_events ORDER BY rowid DESC LIMIT 10000)"
    )


class AuditLog:
    def __init__(self, store):
        self.store = store

    def record(self, operation, outcome="succeeded", *, actor="core", counts=None):
        with self.store.connect() as db:
            record(db, operation, outcome, actor=actor, counts=counts)

    def events(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 1000:
            from .memory import MemoryInputError

            raise MemoryInputError("Audit limit must be between 1 and 1000")
        with self.store.connect() as db:
            return [
                AuditEvent.model_validate_json(row[0]).model_dump(mode="json")
                for row in db.execute(
                    "SELECT data_json FROM audit_events ORDER BY rowid DESC LIMIT ?", (limit,)
                )
            ]

    def clear(self):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
            db.execute("DELETE FROM audit_events")
            record(db, "audit.clear", counts={"deleted": count})
            return {"deleted": count}
