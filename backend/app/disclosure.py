"""Owner-scoped provider disclosure authorization, independent of HTTP/provider credentials."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from .audit import record
from .memory import MemoryConflict, MemoryError, MemoryInputError, MemoryPermissionDenied
from .memory_models import TemporalQuery
from .memory_time import active_at
from .owner_models import DisclosurePolicy, DisclosureSettings


def target_id(base_url: str, model: str):
    if not base_url or not model:
        return None
    return hashlib.sha256(json.dumps([base_url.rstrip("/"), model]).encode()).hexdigest()


def learning_selector(source_id: str):
    # Reserved opaque selector, not a file path. It can never collide with the
    # public/private Markdown selectors, even for an imported unusual source ID.
    return "learning-source/" + hashlib.sha256(source_id.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LearningDisclosure:
    source_id: str
    source_revision: int
    owner_id: str
    entity_revision: int | None
    sensitivity: str
    learning_revision: int
    disclosure_revision: int
    target: str
    document_hash: str


def settings(db):
    rows = dict(
        db.execute(
            "SELECT key,value FROM workspace "
            "WHERE key IN ('disclosure_policy','disclosure_revision')"
        )
    )
    return DisclosureSettings(
        revision=int(rows["disclosure_revision"]),
        policy=DisclosurePolicy.model_validate_json(rows["disclosure_policy"]),
    ).model_dump(mode="json")


class DisclosureManager:
    def __init__(self, store):
        self.store = store

    def settings(self):
        with self.store.connect() as db:
            db.execute("BEGIN")
            return settings(db)

    def configure(self, policy: DisclosurePolicy, expected_revision: int):
        if policy.enabled and policy.target_id is None:
            raise MemoryInputError("Enabled disclosure requires the reviewed provider target ID")
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = settings(db)
            if type(expected_revision) is not int or expected_revision != current["revision"]:
                raise MemoryConflict("Disclosure policy changed; review it again")
            for entity_id in policy.entity_ids or []:
                self.store._entity(db, entity_id)
            db.execute(
                "UPDATE workspace SET value=? WHERE key='disclosure_policy'",
                (policy.model_dump_json(),),
            )
            db.execute(
                "UPDATE workspace SET value=? WHERE key='disclosure_revision'",
                (str(current["revision"] + 1),),
            )
            record(db, "disclosure.configure")
            return settings(db)

    def _learning_grant(
        self,
        db,
        target,
        source_id,
        source_revision,
        disclosure_revision,
        document_hash,
        *,
        allow_sensitive=False,
    ):
        from .learning import LearningPipeline
        from .learning_policy import settings as learning_settings

        if (
            type(allow_sensitive) is not bool
            or type(source_revision) is not int
            or source_revision < 1
            or type(disclosure_revision) is not int
            or disclosure_revision < 1
        ):
            raise MemoryInputError("Invalid semantic disclosure review preconditions")
        if (
            not isinstance(target, str)
            or len(target) != 64
            or any(char not in "0123456789abcdef" for char in target)
        ):
            raise MemoryPermissionDenied("A configured reviewed semantic target is required")
        if (
            not isinstance(document_hash, str)
            or len(document_hash) != 64
            or any(char not in "0123456789abcdef" for char in document_hash)
        ):
            raise MemoryInputError("Semantic source digest must be SHA-256")

        source = LearningPipeline(self.store)._source(db, source_id, source_revision)
        current = settings(db)
        if current["revision"] != disclosure_revision:
            raise MemoryConflict("Disclosure policy changed; review it again")
        policy = DisclosurePolicy.model_validate(current["policy"])
        label = "sensitive" if source["sensitivity"] == "sensitive" else "private"
        if (
            not policy.enabled
            or policy.target_id != target
            or "private" not in policy.namespaces
            or "private" not in policy.labels
            or label not in policy.labels
            or label == "sensitive"
            and not allow_sensitive
            or policy.document_paths is None
            or learning_selector(source_id) not in policy.document_paths
            or policy.entity_ids is not None
            and source["entity_id"] not in policy.entity_ids
        ):
            raise MemoryPermissionDenied(
                "Source is outside the reviewed semantic disclosure boundary"
            )
        owner = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
        if source["owner_id"] != owner:
            raise MemoryPermissionDenied("Source belongs to another workspace owner")
        entity = self.store._entity(db, source["entity_id"])
        return LearningDisclosure(
            source_id,
            source["revision"],
            owner,
            entity["revision"] if entity else None,
            label,
            learning_settings(db)["revision"],
            current["revision"],
            target,
            document_hash,
        )

    def authorize_learning(
        self,
        target,
        source_id,
        source_revision,
        disclosure_revision,
        document_hash,
        *,
        allow_sensitive=False,
    ):
        failure, stamp = None, None
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                stamp = self._learning_grant(
                    db,
                    target,
                    source_id,
                    source_revision,
                    disclosure_revision,
                    document_hash,
                    allow_sensitive=allow_sensitive,
                )
            except MemoryError as error:
                failure = error
                record(db, "disclosure.learning", "denied")
            else:
                record(db, "disclosure.learning", counts={"sources": 1})
        if failure:
            raise failure
        return stamp

    def check_learning(self, db, stamp: LearningDisclosure, *, allow_sensitive=False):
        current = self._learning_grant(
            db,
            stamp.target,
            stamp.source_id,
            stamp.source_revision,
            stamp.disclosure_revision,
            stamp.document_hash,
            allow_sensitive=allow_sensitive,
        )
        if current != stamp:
            raise MemoryConflict("Semantic learning authority changed during delivery")

    def describe_learning(self, source_id, target):
        from .learning import LearningPipeline

        with self.store.connect() as db:
            db.execute("BEGIN")
            source = LearningPipeline(self.store)._source(db, source_id, None)
            current = settings(db)
            permitted = True
            try:
                self._learning_grant(
                    db,
                    target,
                    source_id,
                    source["revision"],
                    current["revision"],
                    "0" * 64,
                    allow_sensitive=True,
                )
            except MemoryError:
                permitted = False
            return {
                "source_id": source_id,
                "source_revision": source["revision"],
                "selector": learning_selector(source_id),
                "target_id": target,
                "disclosure_revision": current["revision"],
                "permitted": permitted,
                "sensitivity": "sensitive" if source["sensitivity"] == "sensitive" else "private",
            }

    def authorize(self, provider_target, matches, *, allow_sensitive=False):
        # Source-value/privacy revalidation precedes authorization; no stored transcript is input.
        selected = self.store.select(TemporalQuery(allow_sensitive=allow_sensitive))
        memories = {f"memory/{row['record']['id']}": row for row in selected}
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            policy = DisclosurePolicy.model_validate(settings(db)["policy"])
            if (
                not policy.enabled
                or policy.target_id != provider_target
                or "private" not in policy.labels
            ):
                record(db, "disclosure.authorize", "denied")
                denied = True
                allowed = []
            else:
                denied = False
                allowed = []
                for namespace, match in matches:
                    path = match.document.path
                    if namespace not in policy.namespaces:
                        continue
                    if namespace == "memory":
                        row = memories.get(path)
                        if not row or row["effective_sensitivity"] not in policy.labels:
                            continue
                        item = row["record"]
                        # Recheck under the policy lock as select's snapshot could have changed.
                        live = db.execute(
                            "SELECT * FROM entries WHERE id=?", (item["id"],)
                        ).fetchone()
                        if (
                            not live
                            or live["revision"] != item["revision"]
                            or not active_at(dict(live), datetime.now(UTC))
                        ):
                            continue
                        if item["entity_id"]:
                            try:
                                entity = self.store._entity(db, item["entity_id"])
                            except (MemoryConflict, MemoryPermissionDenied):
                                continue
                            if (
                                entity["sensitivity"] not in policy.labels
                                or entity["sensitivity"] == "sensitive"
                                and not allow_sensitive
                            ):
                                continue
                        if match.excerpt != f"{item['key']}: {item['content']}":
                            continue
                        if policy.memory_ids is not None and item["id"] not in policy.memory_ids:
                            continue
                        if (
                            item["entity_id"] is not None
                            and policy.entity_ids is not None
                            and item["entity_id"] not in policy.entity_ids
                        ):
                            continue
                    else:
                        label = "private" if namespace == "private" else "public"
                        relative = (
                            path.removeprefix("private/knowledge/")
                            if namespace == "private"
                            else path
                        )
                        if (
                            label not in policy.labels
                            or policy.document_paths is not None
                            and f"{namespace}/{relative}" not in policy.document_paths
                        ):
                            continue
                    allowed.append(match)
                record(db, "disclosure.authorize", counts={"sources": len(allowed)})
        if denied:
            raise MemoryPermissionDenied(
                "Provider disclosure is disabled or outside the reviewed target/data boundary"
            )
        return allowed
