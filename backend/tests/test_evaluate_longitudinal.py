import importlib.util
import sys
from pathlib import Path


def load_evaluator():
    path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_longitudinal.py"
    spec = importlib.util.spec_from_file_location("evaluate_longitudinal", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_longitudinal_metrics_are_repeatable_labeled_and_not_all_zero():
    module = load_evaluator()
    report = module.evaluate()
    assert report == module.evaluate()
    assert report["passed"] and len(report["cases"]) == 20
    metrics = report["metrics"]
    assert metrics["calibration_samples"] >= 6
    assert 0 < metrics["declared_confidence_brier"] < 0.25
    assert metrics["mean_attempted_operations_per_correction"] == 2
    assert metrics["successful_correction_operations"] == 5
    assert metrics["rejected_correction_operations"] == 1


def test_absent_labels_denominators_or_confidence_are_not_fake_perfect_scores():
    module = load_evaluator()
    metrics = module.aggregate([], 0, 0, 0)
    assert metrics["declared_confidence_brier"] is None
    assert metrics["declared_confidence_coverage"] is None
    assert metrics["supported_question_coverage"] is None
    assert metrics["provenance_coverage"] is None


def test_longitudinal_evaluator_detects_broken_live_context(monkeypatch):
    from app.retrieval import PersonalRetriever

    original = PersonalRetriever.retrieve

    def no_evidence(self, request):
        return original(self, request).model_copy(update={"evidence": [], "status": "unknown"})

    monkeypatch.setattr(PersonalRetriever, "retrieve", no_evidence)
    module = load_evaluator()
    report = module.evaluate()
    assert not report["passed"] and report["metrics"]["supported_question_coverage"] == 0
    assert report["metrics"]["declared_confidence_brier"] is None
    assert module.main([]) == 1
