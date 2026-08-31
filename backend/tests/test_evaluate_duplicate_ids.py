"""Tests for evaluation-fixture case ID validation."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

EVALUATOR_PATH = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_collaboration.py"
EVALUATOR_SPEC = importlib.util.spec_from_file_location("evaluate_collaboration", EVALUATOR_PATH)
assert EVALUATOR_SPEC is not None and EVALUATOR_SPEC.loader is not None
evaluator = importlib.util.module_from_spec(EVALUATOR_SPEC)
sys.modules[EVALUATOR_SPEC.name] = evaluator
EVALUATOR_SPEC.loader.exec_module(evaluator)


def _case(case_id: str, *, grounded: bool = True) -> dict[str, Any]:
    return {
        "id": case_id,
        "question": f"Public example question for {case_id}",
        "expected_grounded": grounded,
    }


def _write_cases(tmp_path: Path, cases: list[dict[str, Any]]) -> Path:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    return path


def test_valid_fixture_preserves_case_order(tmp_path: Path) -> None:
    cases = [_case("alpha"), _case("beta", grounded=False), _case("gamma")]

    result = evaluator.load_cases(_write_cases(tmp_path, cases))

    assert [case["id"] for case in result] == ["alpha", "beta", "gamma"]


@pytest.mark.parametrize(
    ("case_ids", "first_position", "duplicate_position"),
    [
        (["unique", "duplicate", "duplicate"], 1, 2),
        (["duplicate", "beta", "gamma", "duplicate"], 0, 3),
    ],
)
def test_duplicate_ids_report_the_id_and_zero_based_positions(
    tmp_path: Path,
    case_ids: list[str],
    first_position: int,
    duplicate_position: int,
) -> None:
    path = _write_cases(tmp_path, [_case(case_id) for case_id in case_ids])
    expected = (
        f"duplicate case id 'duplicate' at zero-based positions "
        f"{first_position} and {duplicate_position}"
    )

    with pytest.raises(ValueError, match=re.escape(expected)):
        evaluator.load_cases(path)


def test_duplicate_fixture_fails_before_knowledge_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_cases(tmp_path, [_case("duplicate"), _case("duplicate")])

    class UnexpectedKnowledgeBase:
        def __init__(self, *_: object, **__: object) -> None:
            raise AssertionError("knowledge loading must not start for an invalid fixture")

    monkeypatch.setattr(evaluator, "KnowledgeBase", UnexpectedKnowledgeBase)

    with pytest.raises(ValueError, match="duplicate case id"):
        evaluator.evaluate(path, tmp_path / "knowledge")


def test_cli_returns_setup_error_for_duplicate_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write_cases(tmp_path, [_case("duplicate"), _case("duplicate")])
    monkeypatch.setattr(
        sys,
        "argv",
        ["evaluate_collaboration.py", "--cases", str(path), "--knowledge-dir", str(tmp_path)],
    )

    assert evaluator.main() == 2
    assert (
        "evaluation setup failed: duplicate case id 'duplicate' at zero-based positions 0 and 1"
        in capsys.readouterr().err
    )
