"""Owner learning governance; real retention effects reviewed through a rolled-back savepoint."""

from collections import Counter
from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from .erasure import TABLES, content, fingerprint, snapshot
from .identity_schema import records
from .learning_policy import settings as learning_settings
from .memory import MemoryConflict, MemoryInputError, MemoryNotFound, record_digest
from .memory_models import ConsolidationPlan, LearningSettings, RetentionPlan, RetentionSettings
from .retention import RetentionManager


class GovernanceState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: str
    observed_at: AwareDatetime
    learning: LearningSettings
    retention: RetentionSettings
    retention_plans: list[RetentionPlan]
    consolidation_plans: list[ConsolidationPlan]


class RetentionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: RetentionPlan
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    removed_counts: dict[str, int]
    forgetting_counts: dict[str, int]
    retained_counts: dict[str, int]


class RetentionApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def plan_digest(plan):
    return fingerprint(
        {
            key: plan[key]
            for key in ("id", "owner_id", "policy_revision", "as_of", "created_at", "targets")
        }
    )


class LearningGovernance:
    def __init__(self, store):
        self.store = store
        self.retention = RetentionManager(store)

    def state(self):
        with self.store.connect() as db:
            db.execute("BEGIN")
            return GovernanceState(
                owner_id=db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[
                    0
                ],
                learning=learning_settings(db),
                observed_at=datetime.now(UTC),
                retention=self.retention._settings(db),
                retention_plans=list(reversed(records(db, "retention_plans")[-100:])),
                consolidation_plans=records(db, "consolidation_plans")[-100:],
            )

    def _plan(self, db, plan_id):
        row = db.execute("SELECT data_json FROM retention_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            raise MemoryNotFound("Retention plan not found")
        plan = RetentionPlan.model_validate_json(row[0]).model_dump(mode="json")
        owner = db.execute("SELECT value FROM workspace WHERE key='owner_id'").fetchone()[0]
        if plan["owner_id"] != owner:
            raise MemoryConflict("Retention plan belongs to another workspace")
        return plan

    def _review(self, db, plan_id):
        plan = self._plan(db, plan_id)
        tables = (*TABLES, "turns")
        before = snapshot(db, tables=tables)
        ids = {target["id"] for target in plan["targets"] if target["table"] == "entries"}
        db.execute("SAVEPOINT retention_review")
        try:
            # Use the real native validation/effects. Already-applied replay has no effects.
            self.retention._apply(db, plan_id)
            after = snapshot(db, tables=tables)
        finally:
            db.execute("ROLLBACK TO retention_review")
            db.execute("RELEASE retention_review")
        removed, forgotten, retained, bindings = Counter(), Counter(), Counter(), []
        refresh_hashes = {
            fingerprint([record_digest(row)])
            for row in before["revisions"].values()
            if row["id"] in ids
        }
        linked_plans = {
            content(row)["id"]
            for row in before["action_plans"].values()
            if ids.intersection(content(row)["invocation"].get("source_ids", []))
        }
        for table in tables:
            for key, row in before[table].items():
                if key not in after[table]:
                    removed[table] += 1
                    bindings.append(["removed", table, key, row])
                elif table == "forgotten" and plan["status"] != "applied" and key in refresh_hashes:
                    forgotten["refreshed"] += 1
                    bindings.append(["refreshed", table, key, row])
                elif (
                    table in {"tasks", "notes", "action_plans"}
                    and ids.intersection(
                        content(row).get("invocation", content(row)).get("source_ids", [])
                    )
                    or table == "action_events"
                    and content(row).get("plan_id") in linked_plans
                ):
                    retained[table] += 1
                    bindings.append(["retained", table, key, row])
            for key in after[table].keys() - before[table].keys():
                if table != "forgotten":
                    raise MemoryInputError("Retention produced an unsupported scope mutation")
                forgotten["added"] += 1
                bindings.append(["added", table, key])
        bindings.sort(key=lambda row: (row[0], row[1], row[2]))
        digest = plan_digest(plan)
        return RetentionReview(
            plan=plan,
            digest=digest,
            scope_digest=fingerprint([digest, bindings]),
            removed_counts=dict(removed),
            forgetting_counts=dict(forgotten),
            retained_counts=dict(retained),
        )

    def review_retention(self, plan_id):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._review(db, plan_id)

    def apply_retention(self, plan_id, approval: RetentionApproval):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            plan = self._plan(db, plan_id)
            if plan_digest(plan) != approval.digest:
                raise MemoryConflict("Retention approval must match the exact reviewed plan")
            if plan["status"] == "applied":
                return plan  # Exact immutable-plan replay, not new scope authorization.
            review = self._review(db, plan_id)
            if review.scope_digest != approval.scope_digest:
                raise MemoryConflict("Retention copy scope changed; review it again")
            return self.retention._apply(db, plan_id)
