"""The browser harness must never accidentally target an owner's real workspace/provider."""

import importlib.util
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

PATH = Path(__file__).resolve().parents[2] / "scripts" / "serve_e2e.py"
spec = importlib.util.spec_from_file_location("serve_e2e", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def marker(root, nonce):
    (root / module.MARKER).write_text(nonce, encoding="utf-8")
    (root / "public").mkdir()


def test_fixture_settings_are_local_and_do_not_adopt_owner_credentials(monkeypatch):
    monkeypatch.setenv("PERSONAL_DATA_DIR", "/synthetic-existing-owner-path")
    monkeypatch.setenv("PERSONAL_TOKEN", "ambient-fixture-token")
    monkeypatch.setenv("LLM_BASE_URL", "https://provider.fixture.invalid/v1")
    monkeypatch.setenv("LLM_API_KEY", "ambient-fixture-key")
    monkeypatch.setenv("LLM_MODEL", "ambient-fixture-model")
    with tempfile.TemporaryDirectory(prefix="agent-me-e2e-") as path:
        root = Path(path)
        nonce = str(uuid4())
        marker(root, nonce)
        (root / ".env").write_text("LLM_MODEL=dotenv-fixture-model\n", encoding="utf-8")
        settings = module.fixture_settings(root, nonce)
        assert Path(settings.personal_data_dir) == root.resolve() / "private"
        assert settings.personal_token == module.FIXTURE_TOKEN
        assert settings.personal_enabled and settings.provider_state == "extractive"
        assert (
            settings.llm_api_key == "" and settings.llm_base_url == "" and settings.llm_model == ""
        )
        assert not (root / "private").exists()


def test_fixture_helper_rejects_arbitrary_owner_paths_before_reading_them(tmp_path):
    with pytest.raises(ValueError, match="freshly owned"):
        module.fixture_settings(tmp_path / "private", str(uuid4()))


def test_fixture_helper_rejects_wrong_marker_and_existing_private_data():
    with tempfile.TemporaryDirectory(prefix="agent-me-e2e-") as path:
        root = Path(path)
        nonce = str(uuid4())
        marker(root, nonce)
        with pytest.raises(ValueError, match="marker"):
            module.fixture_settings(root, str(uuid4()))
        (root / "private").mkdir()
        with pytest.raises(ValueError, match="not already exist"):
            module.fixture_settings(root, nonce)


def test_fixture_helper_rejects_knowledge_symlinks(tmp_path):
    with tempfile.TemporaryDirectory(prefix="agent-me-e2e-") as path:
        root = Path(path)
        nonce = str(uuid4())
        (root / module.MARKER).write_text(nonce, encoding="utf-8")
        try:
            (root / "public").symlink_to(tmp_path, target_is_directory=True)
        except OSError:
            pytest.skip("Symlinks are unavailable on this platform")
        with pytest.raises(ValueError, match="symlink"):
            module.fixture_settings(root, nonce)
