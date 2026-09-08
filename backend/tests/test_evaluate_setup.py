import json
import subprocess
import sys
from pathlib import Path

import pytest

EVALUATOR = Path(__file__).resolve().parents[2] / "scripts/evaluate_collaboration.py"


def run_evaluator(tmp_path, workflow, output, corpus, *, expected=False, extra=()):
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            [
                {
                    "id": "synthetic",
                    "question": "Do lunar habitats exist?",
                    "expected_grounded": expected,
                }
            ]
        ),
        encoding="utf-8",
    )
    return subprocess.run(
        [
            sys.executable,
            str(EVALUATOR),
            "--cases",
            str(cases),
            "--knowledge-dir",
            str(corpus),
            "--workflow",
            workflow,
            *output,
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("workflow", ["baseline", "verified"])
@pytest.mark.parametrize("output", [[], ["--json"], ["--markdown"]])
@pytest.mark.parametrize(
    "kind,code",
    [
        ("missing", "knowledge_corpus_empty"),
        ("empty", "knowledge_corpus_empty"),
        ("file", "knowledge_directory_invalid"),
    ],
)
def test_unusable_corpus_is_setup_error(tmp_path, workflow, output, kind, code):
    corpus = tmp_path / "corpus"
    if kind == "empty":
        corpus.mkdir()
    elif kind == "file":
        corpus.write_text("Synthetic content must not appear in diagnostics.")
    result = run_evaluator(tmp_path, workflow, output, corpus)
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == f"evaluation setup failed: {code}\n"


@pytest.mark.parametrize("workflow", ["baseline", "verified"])
@pytest.mark.parametrize("output", [[], ["--json"], ["--markdown"]])
@pytest.mark.parametrize("expected,exit_code", [(False, 0), (True, 1)])
def test_valid_corpus_preserves_behavior_exit_codes(
    tmp_path, workflow, output, expected, exit_code
):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "example.md").write_text(
        "# Cooking\nBread is made from flour and water.\n", encoding="utf-8"
    )
    result = run_evaluator(
        tmp_path, workflow, output, corpus, expected=expected, extra=("--case-id", "synthetic")
    )
    assert result.returncode == exit_code
    assert result.stderr == ""
    assert "synthetic" in result.stdout


@pytest.mark.parametrize("workflow", ["baseline", "verified"])
@pytest.mark.parametrize("output", [[], ["--json"], ["--markdown"]])
def test_list_does_not_require_a_corpus(tmp_path, workflow, output):
    result = run_evaluator(tmp_path, workflow, output, tmp_path / "missing", extra=("--list",))
    assert result.returncode == 0
    assert result.stdout == "synthetic\n"
    assert result.stderr == ""
