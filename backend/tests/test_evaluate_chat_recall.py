import importlib.util
from pathlib import Path


def load_evaluator():
    path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_chat_recall.py"
    spec = importlib.util.spec_from_file_location("evaluate_chat_recall", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fixture_result_is_repeatable_and_outcomes_cover_the_baseline():
    module = load_evaluator()
    results = module.evaluate()
    assert results == module.evaluate()
    assert len(results) == 24
    assert all(result["current_pass"] for result in results)
    assert any(not result["literal_pass"] for result in results)
    assert any(result["literal_pass"] for result in results)


def test_comparator_detects_loss_of_closed_field_support(monkeypatch):
    import app.chat_recall as recall

    module = load_evaluator()
    monkeypatch.setattr(recall, "_BY_PHRASE", {})
    by_case = {result["case"]: result["current_pass"] for result in module.evaluate()}
    assert not by_case["name-zh"]
    assert not by_case["role-en"]
    assert not by_case["project-deadline"]
    assert by_case["exact-project-note"]
    assert by_case["expired-record"]
    assert module.main([]) == 1
