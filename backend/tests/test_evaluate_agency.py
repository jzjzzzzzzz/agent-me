import importlib.util
import sys
from pathlib import Path


def load_evaluator():
    path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_agency.py"
    spec = importlib.util.spec_from_file_location("evaluate_agency", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_agency_evaluation_is_repeatable_and_checks_real_effects():
    module = load_evaluator()
    results = module.evaluate()
    assert results == module.evaluate()
    assert len(results) == 17
    assert len({result.case_id for result in results}) == 17
    assert all(result.passed for result in results)


def test_agency_evaluation_detects_permission_bypass(monkeypatch):
    from app.agency import Agency

    monkeypatch.setattr(Agency, "_authorize", lambda *args: None)
    module = load_evaluator()
    results = {result.case_id: result.passed for result in module.evaluate()}
    assert not results["disabled-by-default"]
    assert not results["source-label-cannot-be-lowered"]
    assert not results["per-tool-subject-boundary"]
    assert not results["memory-instructions-not-authority"]
    assert module.main() == 1
