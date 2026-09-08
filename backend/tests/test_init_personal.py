from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "init_personal.py"


def load_init_personal():
    spec = spec_from_file_location("init_personal", SCRIPT)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_init_personal_restores_missing_scaffolding(tmp_path, monkeypatch):
    init_personal = load_init_personal()
    monkeypatch.setattr(init_personal, "ROOT", tmp_path)

    init_personal.main()

    private = tmp_path / "private"
    env = private / "personal.env"
    knowledge = private / "knowledge"
    profile = private / "profile-template.json"

    original_env = env.read_bytes()
    original_profile = profile.read_bytes()

    knowledge.rmdir()
    profile.unlink()

    init_personal.main()

    assert env.read_bytes() == original_env
    assert knowledge.is_dir()
    assert profile.read_bytes() == original_profile


def test_init_personal_does_not_overwrite_existing_files(tmp_path, monkeypatch):
    init_personal = load_init_personal()
    monkeypatch.setattr(init_personal, "ROOT", tmp_path)

    init_personal.main()

    private = tmp_path / "private"
    env = private / "personal.env"
    profile = private / "profile-template.json"
    database = private / "twin.sqlite3"
    knowledge_file = private / "knowledge" / "notes.md"

    original_env = env.read_bytes()

    profile.write_text("my own profile", encoding="utf-8")
    database.write_bytes(b"my database")
    knowledge_file.write_text("my notes", encoding="utf-8")

    init_personal.main()

    assert env.read_bytes() == original_env
    assert profile.read_text(encoding="utf-8") == "my own profile"
    assert database.read_bytes() == b"my database"
    assert knowledge_file.read_text(encoding="utf-8") == "my notes"


def test_init_personal_reports_created_and_no_changes(tmp_path, monkeypatch, capsys):
    init_personal = load_init_personal()
    monkeypatch.setattr(init_personal, "ROOT", tmp_path)

    init_personal.main()

    first_output = capsys.readouterr().out

    assert "private/personal.env" in first_output
    assert "private/knowledge/" in first_output
    assert "private/profile-template.json" in first_output

    init_personal.main()

    second_output = capsys.readouterr().out

    assert second_output.strip() == "Workspace already exists; no files changed."
