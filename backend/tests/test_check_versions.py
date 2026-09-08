import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_versions.py"
SPEC = importlib.util.spec_from_file_location("check_versions", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
check_versions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_versions)


@pytest.fixture
def repository(tmp_path, monkeypatch):
    files = {
        "VERSION": "2.0.0\n",
        "backend/pyproject.toml": '[project]\nname="example"\nversion="2.0.0"\n',
        "backend/app/__init__.py": '__version__ = "2.0.0"\n',
        "backend/app/main.py": "app = FastAPI(version=__version__)\n",
        "backend/uv.lock": (
            '[[package]]\nname="third-party"\nversion="9.9.9"\n'
            '[package.source]\nregistry="https://example.invalid"\n'
            '[[package]]\nname="example"\nversion="2.0.0"\n'
            '[package.source]\neditable="."\n'
        ),
        "frontend/package.json": json.dumps({"version": "2.0.0"}),
        "frontend/package-lock.json": json.dumps(
            {"version": "2.0.0", "packages": {"": {"version": "2.0.0"}}}
        ),
    }
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    monkeypatch.setattr(check_versions, "ROOT", tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    "source",
    [
        "app = FastAPI(version=__version__)",
        "app = FastAPI(version = __version__)",
        "app = FastAPI(\n title='Example',\n version=__version__,\n)",
        "raise RuntimeError('must not execute')\napp = FastAPI(version=__version__)",
    ],
)
def test_consistent_metadata_passes_without_executing_source(repository, capsys, source):
    (repository / "backend/app/main.py").write_text(source, encoding="utf-8")
    assert check_versions.main() == 0
    assert "Version consistency check passed (2.0.0)." in capsys.readouterr().out


@pytest.mark.parametrize(
    "source",
    [
        'app = FastAPI(version="0.0.0")',
        "app = FastAPI()",
        '# version=__version__\napp = FastAPI(version="0.0.0")',
        'note = "version=__version__"\napp = FastAPI()',
        "other = FastAPI(version=__version__)\napp = FastAPI()",
        "app = Other(version=__version__)",
        "def factory():\n    app = FastAPI(version=__version__)",
    ],
)
def test_wrong_binding_fails_despite_decoy_text(repository, capsys, source):
    (repository / "backend/app/main.py").write_text(source, encoding="utf-8")
    assert check_versions.main() == 1
    assert (
        "backend/app/main.py: FastAPI metadata must use app.__version__" in capsys.readouterr().err
    )


def test_invalid_python_is_a_diagnostic(repository, capsys):
    (repository / "backend/app/main.py").write_text("app = FastAPI(\n", encoding="utf-8")
    assert check_versions.main() == 1
    assert "backend/app/main.py: invalid Python" in capsys.readouterr().err


@pytest.mark.parametrize(
    "filename,old,new,diagnostic",
    [
        ("backend/pyproject.toml", 'version="2.0.0"', 'version="1.0.0"', "backend/pyproject.toml"),
        ("backend/app/__init__.py", '"2.0.0"', '"1.0.0"', "backend/app/__init__.py"),
        ("backend/uv.lock", 'version="2.0.0"', 'version="1.0.0"', "backend/uv.lock"),
        ("backend/uv.lock", 'editable="."', 'editable="elsewhere"', "backend/uv.lock"),
        ("frontend/package.json", '"2.0.0"', '"1.0.0"', "frontend/package.json"),
        (
            "frontend/package-lock.json",
            '"version": "2.0.0"',
            '"version": "1.0.0"',
            "frontend/package-lock.json (root)",
        ),
        (
            "frontend/package-lock.json",
            '"": {"version": "2.0.0"}',
            '"": {"version": "1.0.0"}',
            "frontend/package-lock.json (package)",
        ),
    ],
)
def test_metadata_drift_is_still_reported(repository, capsys, filename, old, new, diagnostic):
    target = repository / filename
    target.write_text(target.read_text().replace(old, new, 1), encoding="utf-8")
    assert check_versions.main() == 1
    assert f"{diagnostic}: expected '2.0.0', found" in capsys.readouterr().err


@pytest.mark.parametrize("version", ["01.0.0", "2.0", "2.0.0-rc1", "v2.0.0"])
def test_stable_version_rules_remain(repository, capsys, version):
    (repository / "VERSION").write_text(version, encoding="utf-8")
    assert check_versions.main() == 1
    assert "VERSION: expected a stable MAJOR.MINOR.PATCH value" in capsys.readouterr().err
