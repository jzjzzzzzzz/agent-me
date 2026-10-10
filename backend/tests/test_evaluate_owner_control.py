import importlib.util
import sys
from pathlib import Path


def load_evaluator():
    path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_owner_control.py"
    spec = importlib.util.spec_from_file_location("evaluate_owner_control", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_owner_evaluation_is_repeatable_and_checks_real_owner_controls():
    module = load_evaluator()
    results = module.evaluate()
    assert results == module.evaluate() and len(results) == 14
    assert all(result.passed for result in results)
    assert len({result.case_id for result in results}) == 14


def test_owner_evaluation_detects_missing_access_audit(monkeypatch):
    from app.audit import AuditLog

    monkeypatch.setattr(AuditLog, "record", lambda *args, **kwargs: None)
    module = load_evaluator()
    results = {result.case_id: result.passed for result in module.evaluate()}
    assert not results["retrieval-access-audited"]
    assert module.main() == 1
