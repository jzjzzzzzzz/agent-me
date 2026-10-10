import importlib.util
import sys
from pathlib import Path


def load_evaluator():
    path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_retrieval.py"
    spec = importlib.util.spec_from_file_location("evaluate_retrieval", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_retrieval_evaluation_is_repeatable_and_expected_labels_are_explicit():
    module = load_evaluator()
    first = module.evaluate()
    assert first == module.evaluate()
    assert len(first) == 16
    assert len({result.case_id for result in first}) == len(first)
    assert all(result.passed for result in first)


def test_retrieval_evaluation_detects_missing_semantic_field_support(monkeypatch):
    import app.retrieval as retrieval

    module = load_evaluator()
    monkeypatch.setattr(retrieval, "_FACETS", {})
    results = {result.case_id: result.passed for result in module.evaluate()}
    assert not results["name-bilingual-field-support"]
    assert not results["skills-synonym-beyond-lexical"]
    assert module.main() == 1
