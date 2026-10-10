import importlib.util
from pathlib import Path


# The CLI module is imported without changing the package layout of scripts/.
def load_evaluator():
    import sys

    path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_memory.py"
    spec = importlib.util.spec_from_file_location("evaluate_memory", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_memory_evaluation_is_repeatable_and_complete():
    module = load_evaluator()
    first = module.evaluate()
    second = module.evaluate()
    assert first == second
    assert len(first) == 18
    assert len({result.case_id for result in first}) == len(first)
    assert all(result.passed for result in first)


def test_memory_evaluation_detects_missing_retrieval(monkeypatch):
    module = load_evaluator()
    monkeypatch.setattr(module.Store, "context", lambda *_args: [])
    results = {result.case_id: result.passed for result in module.evaluate()}
    assert not results["confirmed-source-grounded"]
    assert not results["confirmed-preference-survives-unrelated-query"]
    assert module.main() == 1
