import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_private_path_guard():
    guard = load_script("check_private_data")
    for path in (
        "private/profile.md",
        ".env",
        ".env.local",
        "twin.sqlite3",
        "twin.sqlite3-journal",
        "twin.db-wal",
        "private-twin-export.json",
    ):
        assert guard.private_path(path), path
    for path in (".env.example", "docs/PERSONAL.md", "backend/app/personal.py"):
        assert not guard.private_path(path), path


def test_initializer_is_private_and_idempotent(tmp_path, monkeypatch):
    initializer = load_script("init_personal")
    monkeypatch.setattr(initializer, "ROOT", tmp_path)
    initializer.main()
    env = tmp_path / "private" / "personal.env"
    first = env.read_text()
    assert "PERSONAL_ENABLED=true" in first
    assert len(first.split("PERSONAL_TOKEN=")[1].strip()) >= 32
    initializer.main()
    assert env.read_text() == first
    assert not (tmp_path / ".env").exists()
