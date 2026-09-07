import importlib.util
import json
import sys
from pathlib import Path

from app.config import Settings

CHECK_KNOWLEDGE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_knowledge.py"
CHECK_KNOWLEDGE_SPEC = importlib.util.spec_from_file_location(
    "check_knowledge", CHECK_KNOWLEDGE_PATH
)
assert CHECK_KNOWLEDGE_SPEC is not None and CHECK_KNOWLEDGE_SPEC.loader is not None
check_module = importlib.util.module_from_spec(CHECK_KNOWLEDGE_SPEC)
sys.modules[CHECK_KNOWLEDGE_SPEC.name] = check_module
CHECK_KNOWLEDGE_SPEC.loader.exec_module(check_module)


def settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_success_lists_relative_paths_in_deterministic_order(tmp_path: Path) -> None:
    (tmp_path / "z.md").write_text("# Z\n\nLast", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "a.md").write_text("# A\n\nFirst", encoding="utf-8")

    result = check_module.check_knowledge(tmp_path, settings())

    assert result == check_module.KnowledgeCheckSuccess(
        status="ok", document_count=2, paths=("nested/a.md", "z.md")
    )


def test_empty_and_missing_corpora_fail_safely(tmp_path: Path) -> None:
    for directory in (tmp_path, tmp_path / "missing-private-directory"):
        result = check_module.check_knowledge(directory, settings())

        assert result == check_module.KnowledgeCheckFailure(
            status="error", code="knowledge_corpus_empty"
        )
        assert str(directory) not in json.dumps(result.__dict__)


def test_rejected_file_failures_return_only_stable_codes(tmp_path: Path) -> None:
    private_name = tmp_path / "private-secret.md"
    private_name.write_bytes(b"\xff")

    result = check_module.check_knowledge(tmp_path, settings())

    assert result == check_module.KnowledgeCheckFailure(
        status="error", code="knowledge_document_unreadable"
    )
    assert "private-secret" not in json.dumps(result.__dict__)


def test_oversized_and_symlinked_files_are_rejected(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.md"
    oversized.write_text("private", encoding="utf-8")
    oversized_result = check_module.check_knowledge(tmp_path, settings(max_document_bytes=1))
    assert oversized_result == check_module.KnowledgeCheckFailure(
        status="error", code="knowledge_document_too_large"
    )

    oversized.unlink()
    target = tmp_path / "target.txt"
    target.write_text("private", encoding="utf-8")
    (tmp_path / "linked.md").symlink_to(target)
    symlink_result = check_module.check_knowledge(tmp_path, settings())
    assert symlink_result == check_module.KnowledgeCheckFailure(
        status="error", code="knowledge_symlink_rejected"
    )


def test_json_output_has_a_stable_shape(tmp_path: Path, capsys) -> None:
    (tmp_path / "profile.md").write_text("# Profile\n\nSafe", encoding="utf-8")

    exit_code = check_module.main(["--knowledge-dir", str(tmp_path), "--json"])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "document_count": 1,
        "paths": ["profile.md"],
        "status": "ok",
    }


def test_error_output_is_machine_readable_and_nonzero(tmp_path: Path, capsys) -> None:
    exit_code = check_module.main(["--knowledge-dir", str(tmp_path), "--json"])

    assert exit_code == 1
    assert json.loads(capsys.readouterr().out) == {
        "code": "knowledge_corpus_empty",
        "status": "error",
    }
