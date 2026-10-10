import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.agent_cli import main


def call(tmp_path, capsys, *args):
    status = main(["--data-dir", str(tmp_path / "workspace"), *args])
    output = capsys.readouterr()
    return status, json.loads(output.out if status != 2 else output.err)


def test_cli_learning_review_recall_and_private_export(tmp_path, capsys):
    status, source = call(tmp_path, capsys, "source", "register", "--name", "Synthetic notes")
    assert status == 0 and not source["approved"]
    status, source = call(
        tmp_path, capsys, "source", "approve", source["id"], "--expected-revision", "1"
    )
    assert status == 0 and source["revision"] == 2
    document = tmp_path / "synthetic.md"
    document.write_text("fact project: SyntheticOrchid", encoding="utf-8")
    status, run = call(
        tmp_path, capsys, "ingest", source["id"], str(document), "--expected-source-revision", "2"
    )
    assert status == 0 and run["status"] == "completed"
    entry_id = run["items"][0]["memory_id"]
    assert call(tmp_path, capsys, "recall", "SyntheticOrchid")[1] == []
    assert call(tmp_path, capsys, "memory", "confirm", entry_id, "--expected-revision", "1")[0] == 0
    assert (
        call(tmp_path, capsys, "recall", "SyntheticOrchid")[1][0]["excerpt"]
        == "project: SyntheticOrchid"
    )
    assert (
        call(tmp_path, capsys, "memory", "origins", entry_id)[1][0]["excerpt"] == "SyntheticOrchid"
    )
    destination = tmp_path / "private-export.json"
    assert call(tmp_path, capsys, "export", str(destination))[0] == 0
    assert json.loads(destination.read_text(encoding="utf-8"))["version"] == 3
    if os.name == "posix":
        assert destination.stat().st_mode & 0o777 == 0o600
    before = destination.read_bytes()
    assert call(tmp_path, capsys, "export", str(destination))[0] == 2
    assert destination.read_bytes() == before
    assert call(tmp_path, capsys, "memory", "delete", entry_id)[0] == 2
    assert call(tmp_path, capsys, "memory", "delete", entry_id, "--yes")[0] == 0
    assert call(tmp_path, capsys, "recall", "SyntheticOrchid")[1] == []
    assert call(tmp_path, capsys, "ingest", source["id"], str(document))[1]["replayed"]


def test_cli_stale_edits_and_replacements_require_reviewed_versions(tmp_path, capsys):
    _, item = call(
        tmp_path,
        capsys,
        "memory",
        "add",
        "--key",
        "project",
        "--content",
        "SyntheticOrchid",
        "--sensitivity",
        "sensitive",
    )
    call(tmp_path, capsys, "memory", "confirm", item["id"], "--expected-revision", "1")
    assert call(tmp_path, capsys, "recall", "SyntheticOrchid")[1] == []
    assert call(tmp_path, capsys, "recall", "SyntheticOrchid", "--allow-sensitive")[1]
    assert (
        call(
            tmp_path,
            capsys,
            "memory",
            "edit",
            item["id"],
            "--content",
            "SyntheticCedar",
            "--expected-revision",
            "0",
        )[0]
        == 2
    )
    assert (
        call(
            tmp_path,
            capsys,
            "memory",
            "edit",
            item["id"],
            "--content",
            "SyntheticCedar",
            "--expected-revision",
            "1",
        )[0]
        == 2
    )
    assert call(tmp_path, capsys, "memory", "show", item["id"])[1]["sensitivity"] == "sensitive"
    _, new = call(
        tmp_path, capsys, "memory", "add", "--key", "project", "--content", "SyntheticMaple"
    )
    assert (
        call(
            tmp_path,
            capsys,
            "memory",
            "confirm",
            new["id"],
            "--expected-revision",
            "1",
            "--replace",
            item["id"],
        )[0]
        == 2
    )
    assert (
        call(
            tmp_path,
            capsys,
            "memory",
            "confirm",
            new["id"],
            "--expected-revision",
            "1",
            "--replace",
            item["id"],
            "--replace-revision",
            item["id"] + ":2",
        )[0]
        == 0
    )
    assert call(tmp_path, capsys, "memory", "list")[1][0]["id"] == new["id"]
    assert len(call(tmp_path, capsys, "memory", "list", "--include-superseded")[1]) == 2


def test_cli_failed_ingestion_exits_nonzero_and_revoke_blocks_replay(tmp_path, capsys):
    _, source = call(tmp_path, capsys, "source", "register", "--name", "Synthetic")
    call(tmp_path, capsys, "source", "approve", source["id"], "--expected-revision", "1")
    document = tmp_path / "synthetic.md"
    document.write_text("Malformed synthetic document", encoding="utf-8")
    status, failed = call(tmp_path, capsys, "ingest", source["id"], str(document))
    assert status == 1 and failed["status"] == "failed"
    assert (
        call(tmp_path, capsys, "source", "revoke", source["id"], "--expected-revision", "2")[0] == 0
    )
    assert call(tmp_path, capsys, "ingest", source["id"], str(document))[0] == 2


def test_cli_runs_without_http_provider_or_environment_configuration(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    code = (
        "import sys; from app.agent_cli import main; "
        "assert main(['--data-dir', sys.argv[1], 'memory', 'list']) == 0; "
        "assert 'fastapi' not in sys.modules; assert 'httpx' not in sys.modules; "
        "assert 'app.config' not in sys.modules; assert 'app.provider' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        cwd=backend,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []


@pytest.mark.skipif(os.name != "posix", reason="POSIX O_NOFOLLOW behavior")
def test_cli_export_never_follows_symlinks(tmp_path, capsys):
    original = tmp_path / "existing.json"
    original.write_text("Keep this", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(original)
    assert call(tmp_path, capsys, "export", str(link), "--force")[0] == 2
    assert original.read_text(encoding="utf-8") == "Keep this"
