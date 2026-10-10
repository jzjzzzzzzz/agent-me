"""Owner-scoped provider disclosure authorization, independent of HTTP/provider credentials."""

import hashlib
import json
from datetime import UTC, datetime

from .audit import record
from .memory import MemoryConflict, MemoryInputError, MemoryPermissionDenied
from .memory_models import TemporalQuery
from .memory_time import active_at
from .owner_models import DisclosurePolicy, DisclosureSettings


def target_id(base_url: str, model: str):
    if not base_url or not model:
        return None
    return hashlib.sha256(json.dumps([base_url.rstrip("/"), model]).encode()).hexdigest()


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
