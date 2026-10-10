"""Explicit owner learning policy; no policy can auto-confirm memory or grant tools."""

import json
import unicodedata

from .memory import MemoryConflict, Store
from .memory_models import LearningPolicy


def key_text(value):
    return unicodedata.normalize("NFC", value.strip()).casefold()


def matches_prefix(key, prefixes):
    return any(key_text(key).startswith(key_text(prefix)) for prefix in prefixes)


def settings(db):
    values = dict(
        db.execute(
            "SELECT key,value FROM workspace WHERE key IN ('learning_policy','learning_revision')"
        )
    )
    return {
        "revision": int(values["learning_revision"]),
        "policy": LearningPolicy.model_validate_json(values["learning_policy"]).model_dump(),
    }


class LearningPolicyManager:
    def __init__(self, store: Store):
        self.store = store

    def settings(self):
        with self.store.connect() as db:
            db.execute("BEGIN")
            return settings(db)

    def configure(self, policy: LearningPolicy, expected_revision: int, *, expected_owner_id=None):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = settings(db)
            owner = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
            if expected_owner_id is not None and expected_owner_id != owner:
                raise MemoryConflict("Learning policy owner changed; review it again")
            if type(expected_revision) is not int or current["revision"] != expected_revision:
                raise MemoryConflict("Learning policy changed; review it again")
            db.execute(
                "UPDATE workspace SET value=? WHERE key='learning_policy'",
                (json.dumps(policy.model_dump()),),
            )
            db.execute(
                "UPDATE workspace SET value=? WHERE key='learning_revision'",
                (str(current["revision"] + 1),),
            )
            return settings(db)
