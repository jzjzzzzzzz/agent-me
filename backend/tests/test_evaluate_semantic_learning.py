import importlib.util
import json
import sys
from pathlib import Path

import pytest


def evaluator():
    path = Path(__file__).resolve().parents[2] / "scripts/evaluate_semantic_learning.py"
    spec = importlib.util.spec_from_file_location("semantic_evaluator", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fixture(module):
    data = module.Dataset.model_validate(module.read_json(module.DEFAULT_DATASET))
    predictions = module.Predictions.model_validate(
        {
            "schema_version": 1,
            "dataset_id": data.dataset_id,
            "producer": "unit-fixture",
            "run_kind": "scripted",
            "cases": [
                {
                    "id": case.id,
                    "response": {
                        "candidates": [item.model_dump(exclude_none=True) for item in case.expected]
                    },
                }
                for case in data.cases
            ],
        }
    )
    return data, predictions


def test_fixture_check_reports_no_model_performance_and_perfect_reference_scoring_is_explicit(
    capsys,
):
    module = evaluator()
    assert module.main(["--check-fixture"]) == 0
    assert "no model performance measured" in capsys.readouterr().out
    data, predictions = fixture(module)
    result = module.score(data, predictions)
    assert result == module.score(data, predictions)
    assert result["declared_run_kind"] == "scripted"
    metrics = result["metrics"]
    assert metrics["cases"] == 12 and metrics["reference_candidates"] == 10
    assert (
        metrics["exact_candidate_precision"]
        == metrics["exact_candidate_recall"]
        == metrics["exact_candidate_f1"]
        == 1
    )
    assert metrics["unsupported_abstention"] == metrics["exact_task_match_rate"] == 1


def test_literal_alignment_is_not_semantic_attribution_or_negation(capsys):
    module = evaluator()
    data, predictions = fixture(module)
    raw = predictions.model_dump()
    row = next(item for item in raw["cases"] if item["id"] == "name-negation")
    row["response"] = {
        "candidates": [{"kind": "fact", "key": "identity.name", "quote": "Alex Example"}]
    }
    report = module.score(data, module.Predictions.model_validate(raw))
    case = next(item for item in report["cases"] if item["case_id"] == "name-negation")
    assert case["status"] == "valid" and case["literal_aligned"] == 1
    assert (
        case["matched"] == 0 and case["false_positives"] == 1 and not case["unsupported_abstention"]
    )
    assert report["metrics"]["individual_literal_alignment"] == 1
    assert report["metrics"]["exact_candidate_precision"] < 1
    assert "Alex Example" not in json.dumps(report)


def test_duplicates_cannot_inflate_true_positives_and_wrong_labels_are_not_matches():
    module = evaluator()
    data, predictions = fixture(module)
    raw = predictions.model_dump()
    row = raw["cases"][0]
    row["response"]["candidates"].append(row["response"]["candidates"][0].copy())
    report = module.score(data, module.Predictions.model_validate(raw))
    case = report["cases"][0]
    assert case["matched"] == 2 and case["submitted"] == 3 and case["false_positives"] == 1
    raw["cases"][0]["response"]["candidates"][0]["key"] = "unrelated.field"
    # The remaining correct duplicate still covers the gold name once.
    assert (
        module.score(data, module.Predictions.model_validate(raw))["cases"][0]["false_positives"]
        == 1
    )
    raw["cases"][0]["response"]["candidates"][2]["key"] = "unrelated.field"
    assert (
        module.score(data, module.Predictions.model_validate(raw))["cases"][0]["false_positives"]
        == 2
    )


def test_invalid_batches_earn_no_partial_match_even_with_valid_quotes():
    module = evaluator()
    data, predictions = fixture(module)
    raw = predictions.model_dump()
    raw["cases"][0]["response"]["candidates"].append(
        {"kind": "fact", "key": "identity.name", "quote": "Invented Person"}
    )
    case = module.score(data, module.Predictions.model_validate(raw))["cases"][0]
    assert case["status"] == "invalid" and case["literal_aligned"] == 2
    assert (
        case["accepted"] == case["matched"] == 0
        and case["false_positives"] == 3
        and case["false_negatives"] == 2
    )


def test_missing_error_and_invalid_empty_are_not_successful_abstention():
    module = evaluator()
    data, predictions = fixture(module)
    raw = predictions.model_dump()
    raw["cases"] = [
        {"id": "name-negation", "response": {}},
        {"id": "third-person-preference", "error": "provider_failure"},
    ]
    report = module.score(data, module.Predictions.model_validate(raw))
    assert report["metrics"]["unsupported_abstention"] == 0
    assert report["metrics"]["case_coverage"] == pytest.approx(2 / 12)
    assert report["metrics"]["valid_batch_rate"] == 0
    assert report["metrics"]["exact_candidate_f1"] == 0


def test_all_empty_outputs_do_not_create_a_perfect_model_score():
    module = evaluator()
    data, predictions = fixture(module)
    raw = predictions.model_dump()
    for case in raw["cases"]:
        case["response"] = {"candidates": []}
    report = module.score(data, module.Predictions.model_validate(raw))["metrics"]
    assert report["exact_candidate_precision"] is None
    assert report["exact_candidate_recall"] == report["exact_candidate_f1"] == 0
    assert report["unsupported_abstention"] == 1 and report["supported_case_coverage"] == 0
    assert report["exact_task_match_rate"] == pytest.approx(5 / 12)


def test_repeated_and_emoji_offsets_use_codepoints_not_value_only_matches():
    module = evaluator()
    data, predictions = fixture(module)
    raw = predictions.model_dump()
    repeated = next(item for item in raw["cases"] if item["id"] == "repeated-owner-name")
    repeated["response"]["candidates"][0]["start"] = 0
    report = module.score(data, module.Predictions.model_validate(raw))
    case = next(item for item in report["cases"] if item["case_id"] == "repeated-owner-name")
    assert case["status"] == "valid" and case["matched"] == 0 and case["false_positives"] == 1
    emoji = next(item for item in raw["cases"] if item["id"] == "mixed-unicode")
    emoji["response"]["candidates"][0]["start"] += 1
    case = next(
        item
        for item in module.score(data, module.Predictions.model_validate(raw))["cases"]
        if item["case_id"] == "mixed-unicode"
    )
    assert case["status"] == "invalid"


@pytest.mark.parametrize("change", ["duplicate", "unknown", "dataset", "version", "outcomes"])
def test_predictions_are_strictly_matched_to_the_task_set(change):
    module = evaluator()
    data, predictions = fixture(module)
    raw = predictions.model_dump()
    if change == "duplicate":
        raw["cases"].append(raw["cases"][0])
    elif change == "unknown":
        raw["cases"][0]["id"] = "not-in-dataset"
    elif change == "dataset":
        raw["dataset_id"] = "different-dataset"
    elif change == "version":
        raw["schema_version"] = True
    else:
        raw["cases"][0]["error"] = "provider_failure"
    with pytest.raises(ValueError):
        module.score(data, module.Predictions.model_validate(raw))


def test_invalid_references_are_not_silently_used_as_ground_truth():
    module = evaluator()
    raw = module.read_json(module.DEFAULT_DATASET)
    raw["cases"][0]["expected"][0]["quote"] = "Invented Person"
    with pytest.raises(module.MemoryInputError):
        module.Dataset.model_validate(raw)
    raw = module.read_json(module.DEFAULT_DATASET)
    raw["cases"][0]["expected"][0]["key"] = "unrequested.field"
    with pytest.raises(ValueError):
        module.Dataset.model_validate(raw)


def test_cli_scores_only_explicit_file_gates_on_request_and_never_echoes_invalid_input(
    tmp_path, capsys
):
    module = evaluator()
    data, predictions = fixture(module)
    path = tmp_path / "predictions.json"
    path.write_text(predictions.model_dump_json(), encoding="utf-8")
    assert module.main(["--predictions", str(path), "--require-perfect"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["declared_run_kind"] == "scripted"
    raw = predictions.model_dump()
    raw["cases"] = []
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert module.main(["--predictions", str(path)]) == 0
    capsys.readouterr()
    assert module.main(["--predictions", str(path), "--require-perfect"]) == 1
    capsys.readouterr()
    path.write_text('{"private-input":"SyntheticSecretDoNotEcho"}', encoding="utf-8")
    assert module.main(["--predictions", str(path)]) == 2
    captured = capsys.readouterr()
    assert "SyntheticSecretDoNotEcho" not in captured.err + captured.out


def test_bounded_and_duplicate_json_inputs_are_rejected(tmp_path):
    module = evaluator()
    path = tmp_path / "input.json"
    path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    with pytest.raises(module.MemoryInputError):
        module.read_json(path)
    path.write_bytes(b"x" * (module.MAX_JSON_BYTES + 1))
    with pytest.raises(ValueError):
        module.read_json(path)
