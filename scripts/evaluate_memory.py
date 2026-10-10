"""Deterministic longitudinal memory evaluation using disposable fictional records."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.memory import Entry, MemoryConflict, Store


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    passed: bool


def rejected_without_mutation(db: Store, action: Callable[[], object]) -> bool:
    before = db.export()
    try:
        action()
    except MemoryConflict:
        return db.export() == before
    return False


def evaluate() -> list[EvaluationResult]:
    results: list[EvaluationResult] = []

    def check(case_id: str, passed: bool):
        results.append(EvaluationResult(case_id, passed))

    # No user workspace, configuration, real identity, or provider is consulted.
    with TemporaryDirectory(prefix="agent-me-memory-eval-") as directory:
        db = Store(directory)
        item = db.add(
            Entry(key="project", content="SyntheticOrchid"), source="turn:synthetic"
        )
        check("pending-excluded", not db.context("SyntheticOrchid"))
        db.confirm(item["id"], [], 1)
        matches = db.context("SyntheticOrchid")
        check(
            "confirmed-source-grounded",
            len(matches) == 1
            and matches[0].document.path == f"memory/{item['id']}"
            and matches[0].excerpt == "project: SyntheticOrchid",
        )
        check("unsupported-excluded", not db.context("SyntheticTulip"))

        db.edit(item["id"], Entry(key="project", content="SyntheticCedar"), 2)
        check("corrected-old-content-excluded", not db.context("SyntheticOrchid"))
        check("correction-requires-review", not db.context("SyntheticCedar"))
        check(
            "stale-approval-rejected",
            rejected_without_mutation(db, lambda: db.confirm(item["id"], [], 2)),
        )
        db.confirm(item["id"], [], 3)
        matches = db.context("SyntheticCedar")
        check(
            "approved-correction-is-retrievable",
            len(matches) == 1 and matches[0].excerpt == "project: SyntheticCedar",
        )
        candidate = db.add(Entry(key="project", content="SyntheticMaple"))
        check(
            "replacement-requires-review",
            rejected_without_mutation(db, lambda: db.confirm(candidate["id"], [])),
        )
        check(
            "stale-replacement-rejected",
            rejected_without_mutation(
                db,
                lambda: db.confirm(candidate["id"], [item["id"]], 1, {item["id"]: 3}),
            ),
        )
        db.confirm(candidate["id"], [item["id"]], 1, {item["id"]: 4})
        check("superseded-excluded", not db.context("SyntheticCedar"))
        matches = db.context("SyntheticMaple")
        check(
            "replacement-is-retrievable",
            len(matches) == 1
            and matches[0].document.path == f"memory/{candidate['id']}"
            and matches[0].excerpt == "project: SyntheticMaple",
        )
        versions = db.revisions(item["id"])
        check(
            "historical-provenance-preserved",
            [version["change"] for version in versions]
            == ["created", "confirmed", "edited", "confirmed", "superseded"]
            and versions[0]["source"] == "turn:synthetic"
            and versions[2]["source"] == "manual"
            and versions[-1]["superseded_by"] == candidate["id"],
        )
        restored = db.restore(item["id"], 2, 5)
        check(
            "restore-is-pending-and-attributable",
            restored["status"] == "pending"
            and restored["source"] == f"memory:{item['id']}@2"
            and not db.context("SyntheticOrchid"),
        )
        db.delete(candidate["id"])
        check("deletion-cannot-reactivate-history", not db.context("SyntheticCedar"))
        db.delete(item["id"])
        exported = db.export()
        check(
            "forget-removes-all-source-revisions",
            all(record["id"] != item["id"] for record in exported["entries"])
            and all(record["id"] != item["id"] for record in exported["revisions"]),
        )
        db.delete(restored["id"])
        preference = db.add(
            Entry(kind="preference", key="response.style", content="Use bullets")
        )
        db.confirm(preference["id"], [])
        check(
            "confirmed-preference-survives-unrelated-query",
            {match.document.path for match in db.context("SyntheticTulip")}
            == {f"memory/{preference['id']}"},
        )
        db.delete(preference["id"])
        check("deleted-preference-excluded", not db.context("SyntheticTulip"))
        check(
            "export-empty-after-forgetting",
            not any(
                db.export()[field]
                for field in ("entries", "history", "revisions", "origins")
            )
            and bool(db.export()["forgotten"]),
        )
    return results


def main() -> int:
    results = evaluate()
    print("case\tresult")
    for result in results:
        print(f"{result.case_id}\t{'PASS' if result.passed else 'FAIL'}")
    passed = sum(result.passed for result in results)
    print(f"\nMEMORY_EVAL {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
