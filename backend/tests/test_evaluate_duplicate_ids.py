"""Unit tests for evaluate_collaboration.load_cases duplicate-ID detection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make the scripts package importable without installing it.
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from evaluate_collaboration import load_cases  # noqa: E402


def _write_cases(tmp_path: Path, cases: list[dict]) -> Path:
    p = tmp_path / "cases.json"
    p.write_text(json.dumps(cases), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_valid_fixture_is_accepted(tmp_path: Path) -> None:
    """Three cases with distinct IDs should load in order without error."""
    cases = [
        {"id": "alpha", "question": "What is alpha?", "expected_grounded": True},
        {"id": "beta", "question": "What is beta?", "expected_grounded": False},
        {"id": "gamma", "question": "What is gamma?", "expected_grounded": True},
    ]
    result = load_cases(_write_cases(tmp_path, cases))
    assert [c["id"] for c in result] == ["alpha", "beta", "gamma"]


def test_single_case_is_accepted(tmp_path: Path) -> None:
    cases = [{"id": "solo", "question": "Only one?", "expected_grounded": False}]
    result = load_cases(_write_cases(tmp_path, cases))
    assert len(result) == 1


# ---------------------------------------------------------------------------
# Duplicate-ID rejection
# ---------------------------------------------------------------------------


def test_adjacent_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    """Duplicate IDs at positions 1 and 2 (adjacent) must be caught."""
    cases = [
        {"id": "unique", "question": "First question.", "expected_grounded": True},
        {"id": "dup", "question": "Second question.", "expected_grounded": False},
        {"id": "dup", "question": "Third question.", "expected_grounded": True},
    ]
    with pytest.raises(ValueError, match="duplicate case id .dup. at positions 1 and 2"):
        load_cases(_write_cases(tmp_path, cases))


def test_non_adjacent_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    """Duplicate IDs at positions 0 and 3 (non-adjacent) must be caught."""
    cases = [
        {"id": "dup", "question": "First question.", "expected_grounded": True},
        {"id": "b", "question": "Second question.", "expected_grounded": False},
        {"id": "c", "question": "Third question.", "expected_grounded": True},
        {"id": "dup", "question": "Fourth question.", "expected_grounded": False},
    ]
    with pytest.raises(ValueError, match="duplicate case id .dup. at positions 0 and 3"):
        load_cases(_write_cases(tmp_path, cases))


def test_duplicate_error_names_the_id(tmp_path: Path) -> None:
    """The error message must include the duplicated ID value."""
    cases = [
        {"id": "my-case-id", "question": "Q1", "expected_grounded": True},
        {"id": "my-case-id", "question": "Q2", "expected_grounded": True},
    ]
    with pytest.raises(ValueError, match="my-case-id"):
        load_cases(_write_cases(tmp_path, cases))


def test_no_cases_executed_after_duplicate_detected(tmp_path: Path) -> None:
    """load_cases must raise before returning, so no cases are silently processed."""
    cases = [
        {"id": "x", "question": "Q1", "expected_grounded": True},
        {"id": "x", "question": "Q2", "expected_grounded": False},
    ]
    with pytest.raises(ValueError):
        load_cases(_write_cases(tmp_path, cases))
