"""Disposable, fictional owner-control acceptance checks; never loads user configuration."""

from __future__ import annotations

import copy
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agency import Agency
from app.agency_models import PermissionInput, ToolInvocation
from app.audit import AuditLog
from app.learning import LearningPipeline
from app.memory import MemoryConflict, MemoryInputError, MemoryPermissionDenied, Store
from app.memory_models import IngestionInput, MemoryExport, SourceInput
from app.owner_control import OwnerControl
from app.owner_models import WorkspacePurge
from app.portability import PortableMemory
from app.retrieval import PersonalRetriever
from app.retrieval_models import AskRequest


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    passed: bool


def blocked(operation):
    try:
        operation()
    except (MemoryConflict, MemoryInputError, MemoryPermissionDenied):
        return True
    return False


def evaluate():
    results = []

    def check(case_id, passed):
        results.append(EvaluationResult(case_id, bool(passed)))

    with TemporaryDirectory(prefix="agent-me-owner-eval-") as directory:
        original = Store(str(Path(directory) / "original"))
        learning = LearningPipeline(original)
        source = learning.register(
            SourceInput(kind="document", name="Fictional source")
        )
        learning.approve(source["id"])
        run = learning.ingest(
            source["id"], IngestionInput(content="fact project: FictionalOrchid")
        )
        memory_id = run["items"][0]["memory_id"]
        original.confirm(memory_id, [], 1)
        agency = Agency(original)
        agency.configure("notes.create", PermissionInput(enabled=True), 1)
        plan = agency.plan(
            ToolInvocation(
                tool="notes.create",
                arguments={
                    "title": "Fictional note",
                    "content": "PrivateFictionalCopy",
                },
                idempotency_key="owner-eval",
            )
        )
        agency.approve(plan["id"], 1, plan["digest"])
        agency.execute(plan["id"])
        snapshot = original.export()
        invalid = PortableMemory(Store(str(Path(directory) / "invalid")))
        check(
            "import-exact-reviewed-digest",
            blocked(lambda: invalid.apply(snapshot, "0" * 64)),
        )
        forged = copy.deepcopy(snapshot)
        forged["entries"][0]["owner_id"] = "forged-owner"
        check("mixed-owner-snapshot-rejected", blocked(lambda: invalid.preview(forged)))
        check(
            "nonempty-destination-rejected",
            blocked(lambda: PortableMemory(original).preview(snapshot)),
        )
        moved = Store(str(Path(directory) / "moved"))
        portable = PortableMemory(moved)
        preview = portable.preview(snapshot)
        check(
            "import-preview-no-effects",
            not moved.entries() and preview["counts"]["entries"] == 1,
        )
        portable.apply(snapshot, preview["digest"])
        check(
            "portable-memory-and-provenance",
            moved.owner_id == original.owner_id
            and bool(moved.context("FictionalOrchid"))
            and MemoryExport.model_validate(moved.export()).origins
            == MemoryExport.model_validate(snapshot).origins,
        )
        check(
            "tool-authority-not-restored",
            all(not item["enabled"] for item in Agency(moved).permissions())
            and not Agency(moved).plans(),
        )
        owner = OwnerControl(moved)
        check(
            "historical-approvals-inert-inspectable",
            len(owner.archives()) == 1
            and owner.archives()[0]["authority"]["action_plans"][0]["status"]
            == "completed",
        )
        check(
            "learning-sources-need-new-review",
            blocked(
                lambda: LearningPipeline(moved).ingest(
                    source["id"],
                    IngestionInput(content="fact project: FictionalOrchid"),
                )
            ),
        )
        PersonalRetriever(moved).retrieve(
            AskRequest(question="UniquePrivateQuestionFictionalOrchid")
        )
        events = AuditLog(moved).events()
        check(
            "retrieval-access-audited",
            any(item["operation"] == "retrieval.retrieve" for item in events),
        )
        check(
            "audit-excludes-private-content",
            "UniquePrivateQuestion" not in json.dumps(events)
            and "PrivateFictionalCopy" not in json.dumps(events),
        )
        note = Agency(moved).notes()[0]
        check(
            "output-erasure-needs-current-revision",
            blocked(lambda: owner.delete_output("notes", note["id"], 99))
            and len(Agency(moved).notes()) == 1,
        )
        owner.delete_output("notes", note["id"], 1)
        check("independent-output-erasure", not Agency(moved).notes())
        source_revision = moved.export()["sources"][0]["revision"]
        owner.delete_source(source["id"], source_revision, forget_memories=True)
        check(
            "derived-memory-forgetting-removes-history",
            not moved.entries()
            and not moved.export()["revisions"]
            and bool(moved.export()["forgotten"]),
        )
        old_owner = moved.owner_id
        owner.purge(
            WorkspacePurge(
                expected_owner_id=old_owner, confirmation="erase-personal-workspace"
            )
        )
        after = moved.export()
        check(
            "purge-erases-archives-and-resets-owner",
            moved.owner_id != old_owner
            and not owner.archives()
            and "PrivateFictionalCopy" not in json.dumps(after)
            and not after["forgotten"],
        )
    return results


def main():
    results = evaluate()
    print("case\tresult")
    for result in results:
        print(f"{result.case_id}\t{'PASS' if result.passed else 'FAIL'}")
    passed = sum(result.passed for result in results)
    print(f"\nOWNER_CONTROL_EVAL {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
