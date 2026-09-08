from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.collaboration import CollaborationOrchestrator
from app.knowledge import KnowledgeBase, KnowledgeLoadError


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    expected_grounded: bool
    actual_grounded: bool
    source_count: int
    critic_outcome: str
    passed: bool


def _markdown_cell(value: str) -> str:
    lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "<br>".join(
        html.escape(line, quote=True).replace("\\", "\\\\").replace("|", "\\|")
        for line in lines
    )


def markdown_summary(results: list[EvaluationResult], workflow: str) -> str:
    passed = sum(result.passed for result in results)
    failed = [result.case_id for result in results if not result.passed]
    lines = [
        f"## Collaboration evaluation — {_markdown_cell(workflow)}",
        "",
        f"**{passed}/{len(results)} cases passed.**",
        "",
        "| Case ID | Expected | Actual | Status |",
        "| --- | --- | --- | --- |",
    ]
    for result in results:
        lines.append(
            "| "
            f"{_markdown_cell(result.case_id)} | "
            f"{'grounded' if result.expected_grounded else 'blocked'} | "
            f"{'grounded' if result.actual_grounded else 'blocked'} | "
            f"{'PASS' if result.passed else 'FAIL'} |"
        )
    failed_text = (
        ", ".join(f"`{_markdown_cell(case_id)}`" for case_id in failed)
        if failed
        else "none"
    )
    lines.extend(("", f"Failed cases: {failed_text}", ""))
    return "\n".join(lines)


def load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("evaluation cases must be a non-empty JSON array")
    cases: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}
    for index, item in enumerate(data):
        if not isinstance(item, dict) or set(item) != {
            "id",
            "question",
            "expected_grounded",
        }:
            raise ValueError(f"case {index} has an invalid shape")
        if (
            not isinstance(item["id"], str)
            or not item["id"].strip()
            or not isinstance(item["question"], str)
            or not item["question"].strip()
            or not isinstance(item["expected_grounded"], bool)
        ):
            raise ValueError(f"case {index} has invalid values")
        case_id = item["id"]
        if case_id in seen_ids:
            raise ValueError(
                f"duplicate case id {case_id!r} at zero-based positions "
                f"{seen_ids[case_id]} and {index}"
            )
        seen_ids[case_id] = index
        cases.append(item)
    return cases


def evaluate(
    cases_path: Path,
    knowledge_dir: Path,
    *,
    verify: bool = False,
    case_ids: list[str] | None = None,
) -> list[EvaluationResult]:
    cases = load_cases(cases_path)
    if case_ids:
        wanted = set(case_ids)
        known = {case["id"] for case in cases}
        unknown = [
            case_id for case_id in dict.fromkeys(case_ids) if case_id not in known
        ]
        if unknown:
            raise ValueError(f"unknown case id {unknown[0]!r}")
        cases = [case for case in cases if case["id"] in wanted]
    knowledge = KnowledgeBase(str(knowledge_dir))
    if not knowledge.documents():
        raise KnowledgeLoadError("knowledge_corpus_empty")
    orchestrator = CollaborationOrchestrator(retriever=knowledge)
    results: list[EvaluationResult] = []
    for case in cases:
        run = orchestrator.run(question=case["question"], verify=verify)
        critic = next(stage for stage in run.trace if stage.agent == "critic")
        expected = case["expected_grounded"]
        results.append(
            EvaluationResult(
                case_id=case["id"],
                expected_grounded=expected,
                actual_grounded=run.grounded,
                source_count=len(run.matches),
                critic_outcome=critic.outcome,
                passed=run.grounded is expected,
            )
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic grounded/unsupported collaboration checks."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=ROOT / "course" / "fixtures" / "collaboration_cases.json",
    )
    parser.add_argument("--knowledge-dir", type=Path, default=ROOT / "knowledge")
    output = parser.add_mutually_exclusive_group()
    output.add_argument(
        "--json", action="store_true", help="emit machine-readable output"
    )
    output.add_argument(
        "--markdown", action="store_true", help="emit a Markdown summary"
    )
    parser.add_argument(
        "--workflow",
        choices=("baseline", "verified"),
        default="baseline",
        help="choose the four-stage baseline or five-stage verified policy",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_cases",
        help="list validated fixture case IDs without running evaluation",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="evaluate one or more case IDs (repeatable)",
    )
    args = parser.parse_args()

    try:
        cases = load_cases(args.cases)
        if args.list_cases:
            print("\n".join(case["id"] for case in cases))
            return 0
        results = evaluate(
            args.cases,
            args.knowledge_dir,
            verify=args.workflow == "verified",
            case_ids=args.case_id,
        )
    except KnowledgeLoadError as error:
        print(f"evaluation setup failed: {error.code}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(f"evaluation setup failed: {error}", file=sys.stderr)
        return 2

    passed = sum(result.passed for result in results)
    if args.json:
        print(
            json.dumps(
                {
                    "results": [asdict(result) for result in results],
                    "summary": {
                        "passed": passed,
                        "total": len(results),
                        "workflow": args.workflow,
                    },
                },
                indent=2,
            )
        )
    elif args.markdown:
        print(markdown_summary(results, args.workflow), end="")
    else:
        print("case\texpected\tactual\tsources\tcritic\tresult")
        for result in results:
            print(
                f"{result.case_id}\t{result.expected_grounded}\t"
                f"{result.actual_grounded}\t{result.source_count}\t"
                f"{result.critic_outcome}\t{'PASS' if result.passed else 'FAIL'}"
            )
        print(f"\nCOLLABORATION_EVAL {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
