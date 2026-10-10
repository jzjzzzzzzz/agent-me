import importlib.util
import sys
from pathlib import Path


def load_evaluator():
    path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_learning.py"
    spec = importlib.util.spec_from_file_location("evaluate_learning", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_learning_evaluation_is_repeatable_and_covers_real_state():
    module = load_evaluator()
    first = module.evaluate()
    assert first == module.evaluate()
    assert len(first) == 17
    assert len({result.case_id for result in first}) == len(first)
    assert all(result.passed for result in first)


def test_learning_evaluation_detects_missing_grounding(monkeypatch):
    module = load_evaluator()
    monkeypatch.setattr(module.Store, "context", lambda *_args, **_kwargs: [])
    results = {result.case_id: result.passed for result in module.evaluate()}
    assert not results["owner-opt-in-allows-selected-sensitive-context"]
    assert not results["accepted-update-retrievable"]
    assert module.main() == 1
