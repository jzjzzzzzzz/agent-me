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


def test_cli_disclosure_policy_is_owner_configured_without_loading_credentials(tmp_path, capsys):
    assert call(tmp_path, capsys, "disclosure", "policy")[1]["policy"]["enabled"] is False
    status, configured = call(
        tmp_path,
        capsys,
        "disclosure",
        "configure",
        "--expected-revision",
        "1",
        "--policy-json",
        json.dumps(
            {
                "enabled": True,
                "target_id": "f" * 64,
                "namespaces": ["memory"],
                "labels": ["private"],
            }
        ),
    )
    assert status == 0 and configured["revision"] == 2
    assert (
        call(
            tmp_path,
            capsys,
            "disclosure",
            "configure",
            "--expected-revision",
            "1",
            "--policy-json",
            '{"enabled":false}',
        )[0]
        == 2
    )


def test_cli_reviewed_portable_import_audit_and_workspace_erasure(tmp_path, capsys):
    from app.memory import Entry, Store

    original = Store(str(tmp_path / "original"))
    item = original.add(Entry(key="project", content="UniqueFictionalPrivateMarker"))
    original.confirm(item["id"], [], 1)
    file = tmp_path / "snapshot.json"
    file.write_text(json.dumps(original.export()), encoding="utf-8")
    status, preview = call(tmp_path, capsys, "portability", "preview", str(file))
    assert status == 0 and not preview["executable_plans_restored"]
    assert (
        call(tmp_path, capsys, "portability", "import", str(file), "--digest", preview["digest"])[0]
        == 2
    )
    assert (
        call(tmp_path, capsys, "portability", "import", str(file), "--digest", "0" * 64, "--yes")[0]
        == 2
    )
    status, imported = call(
        tmp_path, capsys, "portability", "import", str(file), "--digest", preview["digest"], "--yes"
    )
    assert status == 0 and imported["imported"]
    assert (
        call(tmp_path, capsys, "memory", "list")[1][0]["content"] == "UniqueFictionalPrivateMarker"
    )
    status, events = call(tmp_path, capsys, "audit", "events")
    assert status == 0 and "UniqueFictionalPrivateMarker" not in json.dumps(events)
    assert any(item["operation"] == "cli.memory.list" for item in events)
    assert (
        call(tmp_path, capsys, "owner", "purge", "--expected-owner-id", imported["owner_id"])[0]
        == 2
    )
    assert (
        call(
            tmp_path, capsys, "owner", "purge", "--expected-owner-id", imported["owner_id"], "--yes"
        )[0]
        == 0
    )
    assert call(tmp_path, capsys, "memory", "list")[1] == []
    assert call(tmp_path, capsys, "audit", "clear")[0] == 2
    assert call(tmp_path, capsys, "audit", "clear", "--yes")[0] == 0


def test_cli_owner_erasure_requires_exact_review_and_yes(tmp_path, capsys):
    from app.agency import Agency
    from app.agency_models import PermissionInput, ToolInvocation
    from app.memory import Store

    db = Store(str(tmp_path / "workspace"))
    agency = Agency(db)
    agency.configure("tasks.create", PermissionInput(enabled=True), 1)
    plan = agency.plan(
        ToolInvocation(
            tool="tasks.create",
            arguments={"title": "FictionalTaskCopy"},
            idempotency_key="cli-erase",
        )
    )
    agency.approve(plan["id"], 1, plan["digest"])
    completed = agency.execute(plan["id"])
    output_id = completed["result"]["id"]
    args = ["owner", "delete-output", "tasks", output_id, "--expected-revision", "1"]
    assert call(tmp_path, capsys, *args)[0] == 2
    assert call(tmp_path, capsys, *args, "--yes")[0] == 0
    assert not agency.tasks() and not agency.plans()


def test_cli_learning_policy_and_digest_reviewed_consolidation(tmp_path, capsys):
    assert call(tmp_path, capsys, "learning", "policy")[1]["revision"] == 1
    status, result = call(
        tmp_path,
        capsys,
        "learning",
        "configure",
        "--expected-revision",
        "1",
        "--policy-json",
        '{"require_revision_key_prefixes":["profile."]}',
    )
    assert status == 0 and result["revision"] == 2
    for _ in range(2):
        assert (
            call(
                tmp_path,
                capsys,
                "memory",
                "add",
                "--key",
                "project",
                "--content",
                "Fictional Orchid",
            )[0]
            == 0
        )
    status, plan = call(tmp_path, capsys, "consolidate", "preview")
    assert status == 0 and len(plan["groups"]) == 1
    assert (
        call(tmp_path, capsys, "consolidate", "apply", plan["id"], "--digest", plan["digest"])[0]
        == 2
    )
    status, applied = call(
        tmp_path, capsys, "consolidate", "apply", plan["id"], "--digest", plan["digest"], "--yes"
    )
    assert status == 0 and applied["merged_count"] == 1
    assert len(call(tmp_path, capsys, "memory", "list")[1]) == 1


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
    assert json.loads(destination.read_text(encoding="utf-8"))["version"] == 8
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


def test_cli_identity_bound_memory_relationship_and_time_controls(tmp_path, capsys):
    _, person = call(
        tmp_path,
        capsys,
        "entity",
        "add",
        "--kind",
        "person",
        "--name",
        "Alex Example",
        "--alias",
        "Alex",
    )
    assert (
        call(tmp_path, capsys, "entity", "confirm", person["id"], "--expected-revision", "1")[0]
        == 0
    )
    assert call(tmp_path, capsys, "entity", "resolve", "Alex")[1]["status"] == "resolved"
    _, project = call(
        tmp_path, capsys, "entity", "add", "--kind", "project", "--name", "Orchid Demo"
    )
    call(tmp_path, capsys, "entity", "confirm", project["id"], "--expected-revision", "1")
    _, memory = call(
        tmp_path,
        capsys,
        "memory",
        "add",
        "--key",
        "project.role",
        "--content",
        "Alex works on Orchid",
        "--entity-id",
        person["id"],
        "--confidence",
        "0.8",
    )
    call(tmp_path, capsys, "memory", "confirm", memory["id"], "--expected-revision", "1")
    _, edge = call(
        tmp_path,
        capsys,
        "relationship",
        "add",
        "--from-entity-id",
        person["id"],
        "--to-entity-id",
        project["id"],
        "--predicate",
        "works_on",
        "--evidence-id",
        memory["id"],
    )
    call(tmp_path, capsys, "relationship", "confirm", edge["id"], "--expected-revision", "1")
    assert call(tmp_path, capsys, "entity", "neighbours", person["id"])[1]["relationships"]
    selected = call(tmp_path, capsys, "select", "--entity-id", person["id"])[1]
    assert selected[0]["record"]["confidence"] == 0.8
    assert (
        call(
            tmp_path,
            capsys,
            "memory",
            "edit",
            memory["id"],
            "--content",
            "UncertainCedar",
            "--belief",
            "disputed",
            "--expected-revision",
            "2",
        )[0]
        == 0
    )
    call(tmp_path, capsys, "memory", "confirm", memory["id"], "--expected-revision", "3")
    assert call(tmp_path, capsys, "select")[1] == []
    assert (
        call(tmp_path, capsys, "select", "--include-uncertain")[1][0]["effective_belief"]
        == "disputed"
    )


def test_cli_retention_is_previewed_and_requires_explicit_apply(tmp_path, capsys):
    _, item = call(
        tmp_path,
        capsys,
        "memory",
        "add",
        "--key",
        "project",
        "--content",
        "ExpiredOrchid",
        "--valid-until",
        "2020-01-01T00:00:00Z",
    )
    call(tmp_path, capsys, "memory", "confirm", item["id"], "--expected-revision", "1")
    assert (
        call(
            tmp_path,
            capsys,
            "retention",
            "configure",
            "--policy-json",
            '{"expired_days":1}',
            "--expected-revision",
            "1",
        )[0]
        == 0
    )
    _, plan = call(tmp_path, capsys, "retention", "preview")
    assert plan["targets"][0]["id"] == item["id"]
    assert call(tmp_path, capsys, "retention", "apply", plan["id"])[0] == 2
    assert (
        call(tmp_path, capsys, "retention", "apply", plan["id"], "--yes")[1]["deleted_counts"][
            "entries"
        ]
        == 1
    )


def test_cli_grounded_ask_retrieve_and_verify_without_server(tmp_path, capsys):
    _, item = call(
        tmp_path, capsys, "memory", "add", "--key", "identity.name", "--content", "Alex Example"
    )
    call(tmp_path, capsys, "memory", "confirm", item["id"], "--expected-revision", "1")
    status, answer = call(tmp_path, capsys, "ask", "我的名字是什么")
    assert (
        status == 0 and answer["status"] == "known" and answer["mode"] == "personal-grounded-local"
    )
    assert call(tmp_path, capsys, "ask", "What drug should I take?")[1]["status"] == "unknown"
    request = tmp_path / "verify.json"
    request.write_text(
        json.dumps(
            {"request": {"question": "我的名字是什么"}, "claims": [answer["claims"][0]["claim"]]}
        ),
        encoding="utf-8",
    )
    assert call(tmp_path, capsys, "verify", str(request))[1][0]["verdict"] == "verified"
    call(tmp_path, capsys, "memory", "delete", item["id"], "--yes")
    assert call(tmp_path, capsys, "verify", str(request))[1][0]["verdict"] == "unsupported"


def test_cli_owner_binding_and_temporal_project_question(tmp_path, capsys):
    _, owner = call(tmp_path, capsys, "entity", "add", "--kind", "person", "--name", "Alex Example")
    call(tmp_path, capsys, "entity", "confirm", owner["id"], "--expected-revision", "1")
    assert call(tmp_path, capsys, "entity", "owner", owner["id"])[1]["entity_id"] == owner["id"]
    _, memory = call(
        tmp_path,
        capsys,
        "memory",
        "add",
        "--key",
        "projects.current",
        "--content",
        "OldOrchid",
        "--entity-id",
        owner["id"],
        "--valid-from",
        "2019-01-01T00:00:00Z",
        "--valid-until",
        "2021-01-01T00:00:00Z",
    )
    call(tmp_path, capsys, "memory", "confirm", memory["id"], "--expected-revision", "1")
    answer = call(tmp_path, capsys, "ask", "我的项目在 2020年是什么？")[1]
    assert answer["status"] == "known" and "OldOrchid" in answer["answer"]
    assert call(tmp_path, capsys, "entity", "owner", "--clear")[1]["entity_id"] is None


def test_cli_explicit_permission_plan_approval_and_reversible_effect(tmp_path, capsys):
    assert all(not item["enabled"] for item in call(tmp_path, capsys, "tools", "permissions")[1])
    assert (
        call(
            tmp_path,
            capsys,
            "tools",
            "configure",
            "tasks.create",
            "--policy-json",
            '{"enabled":true}',
            "--expected-revision",
            "1",
        )[0]
        == 0
    )
    invocation = tmp_path / "action.json"
    invocation.write_text(
        json.dumps(
            {
                "tool": "tasks.create",
                "arguments": {"title": "Synthetic demo"},
                "idempotency_key": "cli-demo",
            }
        ),
        encoding="utf-8",
    )
    _, plan = call(tmp_path, capsys, "action", "plan", str(invocation))
    assert plan["status"] == "planned" and call(tmp_path, capsys, "tasks")[1] == []
    assert call(tmp_path, capsys, "action", "execute", plan["id"], "--yes")[0] == 2
    assert (
        call(
            tmp_path,
            capsys,
            "action",
            "approve",
            plan["id"],
            "--expected-revision",
            "1",
            "--digest",
            plan["digest"],
        )[0]
        == 0
    )
    assert call(tmp_path, capsys, "action", "execute", plan["id"])[0] == 2
    assert (
        call(tmp_path, capsys, "action", "execute", plan["id"], "--yes")[1]["status"] == "completed"
    )
    assert len(call(tmp_path, capsys, "tasks")[1]) == 1
    assert (
        call(tmp_path, capsys, "action", "rollback", plan["id"], "--yes")[1]["status"]
        == "rolled_back"
    )
    assert call(tmp_path, capsys, "tasks")[1] == []


def test_cli_typed_runtime_is_local_and_never_executes_a_recommendation(tmp_path, capsys):
    request = tmp_path / "agent.json"
    request.write_text(
        json.dumps(
            {
                "intent": {
                    "kind": "recommend",
                    "invocation": {
                        "tool": "notes.create",
                        "arguments": {"title": "Synthetic", "content": "Fictional note"},
                        "idempotency_key": "recommend",
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    status, result = call(tmp_path, capsys, "agent", str(request))
    assert (
        status == 0
        and result["kind"] == "recommendation"
        and result["result"]["status"] == "recommended"
    )
    assert call(tmp_path, capsys, "notes")[1] == []
    request.write_text(
        json.dumps(
            {"intent": {"kind": "ask", "request": {"question": "What do you know about me?"}}}
        ),
        encoding="utf-8",
    )
    assert call(tmp_path, capsys, "agent", str(request))[1]["kind"] == "knowledge"
