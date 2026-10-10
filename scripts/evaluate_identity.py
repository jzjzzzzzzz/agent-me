"""Deterministic identity, temporal and retention acceptance checks on fictional data."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.identity import IdentityStore
from app.memory import Entry, Store
from app.memory_models import (
    EntityInput,
    RelationshipInput,
    RetentionPolicy,
    TemporalQuery,
)
from app.retention import RetentionManager


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    passed: bool


def evaluate():
    results = []

    def check(case_id, passed):
        results.append(EvaluationResult(case_id, bool(passed)))

    with TemporaryDirectory(prefix="agent-me-identity-eval-") as directory:
        db = Store(directory)
        identity = IdentityStore(db)
        person = identity.add(
            EntityInput(kind="person", name="Alex Example", aliases=["Alex"])
        )
        check(
            "pending-identity-not-resolved",
            identity.resolve("Alex")["status"] == "unknown",
        )
        identity.confirm(person["id"], 1)
        check(
            "approved-alias-resolves",
            identity.resolve("alex")["matches"][0]["id"] == person["id"],
        )
        other = identity.add(
            EntityInput(kind="person", name="Other Example", aliases=["Alex"])
        )
        identity.confirm(other["id"], 1)
        check(
            "ambiguous-alias-not-auto-merged",
            identity.resolve("Alex")["status"] == "ambiguous",
        )
        project = identity.add(EntityInput(kind="project", name="Orchid Demo"))
        identity.confirm(project["id"], 1)
        item = db.add(
            Entry(
                key="project.role",
                content="Alex works on Orchid",
                entity_id=person["id"],
                confidence=0.8,
            )
        )
        db.confirm(item["id"], [])
        check(
            "record-ownership-explicit",
            item["owner_id"] == person["owner_id"] == db.owner_id,
        )
        check(
            "entity-scoped-facts-retrievable",
            bool(db.context("Orchid", entity_id=person["id"])),
        )
        check(
            "different-entity-does-not-borrow-facts",
            not db.context("Orchid", entity_id=other["id"]),
        )
        edge = identity.relate(
            RelationshipInput(
                from_entity_id=person["id"],
                to_entity_id=project["id"],
                predicate="works_on",
                evidence_id=item["id"],
            )
        )
        check(
            "relationship-requires-owner-review",
            not identity.neighbours(person["id"])["relationships"],
        )
        identity.confirm(edge["id"], 1, relationship=True)
        check(
            "reviewed-evidence-linked-relationship-visible",
            len(identity.neighbours(person["id"])["relationships"]) == 1,
        )
        past = datetime.now(UTC)
        db.edit(
            item["id"],
            Entry(
                key="project.role", content="Alex left Orchid", sensitivity="sensitive"
            ),
            2,
        )
        check(
            "changed-evidence-invalidates-relationship",
            not identity.neighbours(person["id"])["relationships"],
        )
        check(
            "history-cannot-bypass-current-privacy",
            not db.context("Orchid", known_at=past),
        )
        check(
            "owner-can-inspect-approved-history",
            bool(db.context("Orchid", known_at=past, allow_sensitive=True)),
        )
        identity.delete(person["id"])
        check(
            "identity-forgetting-purges-history",
            not db.context("Orchid", known_at=past, allow_sensitive=True)
            and identity.resolve("Alex Example")["status"] == "unknown",
        )
        expired = db.add(
            Entry(
                key="project",
                content="ExpiredCedar",
                valid_until="2020-01-01T00:00:00Z",
            )
        )
        db.confirm(expired["id"], [])
        check("expired-fact-not-current", not db.context("ExpiredCedar"))
        check(
            "valid-time-retrospective-supported",
            bool(db.context("ExpiredCedar", as_of="2019-01-01T00:00:00Z")),
        )
        check(
            "valid-time-not-confused-with-learning-time",
            not db.context(
                "ExpiredCedar",
                as_of="2019-01-01T00:00:00Z",
                known_at="2019-01-01T00:00:00Z",
            ),
        )
        future = db.add(
            Entry(
                key="future",
                content="FutureMaple",
                valid_from=datetime.now(UTC) + timedelta(days=365),
            )
        )
        db.confirm(future["id"], [])
        check("future-fact-not-yet-current", not db.context("FutureMaple"))
        disputed = db.add(
            Entry(
                key="dispute",
                content="DisputedBirch",
                belief="disputed",
                confidence=0.4,
            )
        )
        db.confirm(disputed["id"], [])
        check(
            "dispute-inspectable-not-asserted",
            not db.context("DisputedBirch")
            and any(
                row["effective_belief"] == "disputed"
                for row in db.select(TemporalQuery(include_uncertain=True))
            ),
        )
        manager = RetentionManager(db)
        manager.configure(RetentionPolicy(expired_days=1), 1)
        plan = manager.preview()
        check(
            "retention-preview-not-execution",
            any(row["id"] == expired["id"] for row in db.entries())
            and len(plan["targets"]) == 1,
        )
        applied = manager.apply(plan["id"])
        check(
            "retention-apply-is-idempotent-forgetting",
            applied["deleted_counts"]["entries"] == 1
            and manager.apply(plan["id"]) == applied
            and not db.context("ExpiredCedar", as_of="2019-01-01T00:00:00Z"),
        )
    return results


def main():
    results = evaluate()
    print("case\tresult")
    for result in results:
        print(f"{result.case_id}\t{'PASS' if result.passed else 'FAIL'}")
    passed = sum(result.passed for result in results)
    print(f"\nIDENTITY_EVAL {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
