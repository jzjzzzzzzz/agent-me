"""Fictional CLI learning: explicit files/consent, real HTTP boundary, no ambient authority."""

import hashlib
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.agent_cli import main
from app.audit import AuditLog
from app.config import Settings
from app.disclosure import DisclosureManager, learning_selector, target_id
from app.learning import LearningPipeline
from app.memory import Store
from app.memory_models import SourceInput
from app.owner_models import DisclosurePolicy
from app.semantic_cli import MAX_CONFIG_BYTES, ExplicitProvider, load_provider
from app.semantic_learning import EXTRACTOR, INSTRUCTIONS

TEXT = "🪴 我叫示例林。我偏好简短回答。"
PROPOSALS = {
    "candidates": [{"kind": "fact", "key": "identity.name", "quote": "示例林", "start": 4}]
}
KEY = "cli-fixture-only-secret"
REAL_CLIENT = httpx.AsyncClient


def setup(tmp_path, *, sensitivity="private", base_url="https://provider.fixture.invalid/v1"):
    store = Store(tmp_path / "workspace")
    pipeline = LearningPipeline(store)
    source = pipeline.register(
        SourceInput(kind="document", name="Never send registry name", sensitivity=sensitivity)
    )
    source = pipeline.approve(source["id"], expected_revision=1)
    provider_file = tmp_path / "fixture-provider.json"
    values = {"llm_base_url": base_url, "llm_model": "fixture-only-model", "llm_api_key": KEY}
    provider_file.write_text(json.dumps(values), encoding="utf-8")
    content_file = tmp_path / "fixture-source.txt"
    content_file.write_text(TEXT, encoding="utf-8")
    target = target_id(base_url, values["llm_model"])
    manager = DisclosureManager(store)
    manager.configure(
        DisclosurePolicy(
            enabled=True,
            target_id=target,
            namespaces=["private"],
            labels=["private", "sensitive"],
            document_paths=[learning_selector(source["id"])],
        ),
        1,
    )
    return SimpleNamespace(
        store=store,
        pipeline=pipeline,
        source=source,
        provider_file=provider_file,
        content_file=content_file,
        target=target,
        manager=manager,
        values=values,
    )


def command(fixture, action="ingest", *, consent=True):
    args = [
        "--data-dir",
        str(fixture.store.root),
        "semantic",
        action,
        fixture.source["id"],
        str(fixture.content_file),
        "--provider-config",
        str(fixture.provider_file),
    ]
    if action == "ingest":
        args += [
            "--expected-source-revision",
            "2",
            "--expected-disclosure-revision",
            "2",
            "--reviewed-target-id",
            fixture.target,
            "--reviewed-content-hash",
            hashlib.sha256(TEXT.encode()).hexdigest(),
        ]
        if consent:
            args += ["--allow-provider"]
    return args


def invoke(capsys, args):
    status = main(args)
    result = capsys.readouterr()
    assert (
        KEY not in result.out + result.err
        and "https://provider.fixture.invalid" not in result.out + result.err
    )
    assert not result.out if status == 2 else not result.err
    return status, json.loads(result.err if status == 2 else result.out)


def model(monkeypatch, *, proposals=PROPOSALS, callback=None, response=None):
    requests = []

    def send(request):
        requests.append(request)
        if callback:
            callback(request)
        if response:
            return response(request)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(proposals)}}]}
        )

    transport = httpx.MockTransport(send)
    monkeypatch.setattr(
        "app.semantic_learning.httpx.AsyncClient",
        lambda **kwargs: REAL_CLIENT(**{**kwargs, "transport": transport}),
    )
    return requests


def test_review_is_local_opaque_content_bound_and_does_not_grant_disclosure(
    tmp_path, capsys, monkeypatch
):
    fixture = setup(tmp_path)
    fixture.manager.configure(DisclosurePolicy(), 2)
    requests = model(monkeypatch)
    status, review = invoke(capsys, command(fixture, "review"))
    assert status == 0 and not review["permitted"] and review["configured"]
    assert review["target_id"] == fixture.target and review["disclosure_revision"] == 3
    assert review["content_hash"] == hashlib.sha256(TEXT.encode()).hexdigest()
    assert review["source_chars"] == len(TEXT) and review["source_bytes"] == len(TEXT.encode())
    assert review["max_source_chars"] == 12000 - len(INSTRUCTIONS) and review["source_fits_budget"]
    assert review["selector"] == learning_selector(fixture.source["id"])
    assert TEXT not in json.dumps(review) and not requests and not fixture.pipeline.runs()
    assert not fixture.manager.settings()["policy"]["enabled"]


def test_explicit_configuration_ignores_all_settings_sources(tmp_path, monkeypatch):
    fixture = setup(tmp_path)
    for field in Settings.model_fields:
        monkeypatch.setenv(field.upper(), "ambient-value-must-not-be-read")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("LLM_API_KEY=ambient-dotenv-must-not-be-read\n")
    monkeypatch.setattr(
        Settings, "__init__", lambda *args, **kwargs: pytest.fail("BaseSettings sources used")
    )
    config = load_provider(fixture.provider_file)
    assert config.llm_api_key == KEY and config.llm_base_url == fixture.values["llm_base_url"]
    assert config.llm_model == fixture.values["llm_model"] and config.max_context_chars == 12000
    assert config.personal_token == "" and not config.personal_enabled
    assert config.knowledge_dir == "knowledge" and config.provider_timeout_seconds == 60
    assert KEY not in repr(ExplicitProvider.model_validate(fixture.values))


def test_ingestion_stays_pending_keeps_original_origins_and_replays_without_delivery(
    tmp_path, capsys, monkeypatch
):
    fixture = setup(tmp_path)
    requests = model(monkeypatch)
    args = command(fixture)
    status, run = invoke(capsys, args)
    assert status == 0 and run["status"] == "completed" and not run["replayed"]
    assert run["extractor"] == f"{EXTRACTOR}/{fixture.target}" and len(requests) == 1
    outbound = json.loads(requests[0].content)
    assert outbound["messages"] == [
        {"role": "system", "content": INSTRUCTIONS},
        {"role": "user", "content": TEXT},
    ]
    assert requests[0].headers["authorization"] == f"Bearer {KEY}"
    row = fixture.store.entries()[0]
    assert row["status"] == "pending" and row["content"] == "示例林" and row["confidence"] is None
    origin = fixture.pipeline.origins(row["id"])[0]
    assert origin["start"] == 4 and TEXT[origin["start"] : origin["end"]] == row["content"]
    assert (
        origin["document_hash"] == run["document_hash"] == hashlib.sha256(TEXT.encode()).hexdigest()
    )
    assert fixture.store.context("示例林") == []
    status, replay = invoke(capsys, args)
    assert status == 0 and replay["replayed"] and replay["id"] == run["id"] and len(requests) == 1
    fixture.store.delete(row["id"])
    assert (
        invoke(capsys, args)[1]["replayed"] and len(requests) == 1 and not fixture.store.entries()
    )
    audit = json.dumps(AuditLog(fixture.store).events())
    assert TEXT not in audit and KEY not in audit and "示例林" not in audit
    assert any(
        event["operation"] == "cli.semantic.ingest" for event in AuditLog(fixture.store).events()
    )


def test_no_consent_denies_before_reading_config_or_source(tmp_path, capsys, monkeypatch):
    fixture = setup(tmp_path)
    fixture.provider_file.unlink()
    fixture.content_file.unlink()
    requests = model(monkeypatch)
    status, error = invoke(capsys, command(fixture, consent=False))
    assert status == 2 and "--allow-provider" in error["error"]
    assert not requests and not fixture.store.entries() and not fixture.pipeline.runs()


@pytest.mark.parametrize("field", ["llm_base_url", "llm_model", "llm_api_key"])
def test_missing_configured_field_never_falls_back_to_ambient_credentials(
    tmp_path, capsys, monkeypatch, field
):
    fixture = setup(tmp_path)
    for name, value in fixture.values.items():
        monkeypatch.setenv(name.upper(), value)
    values = dict(fixture.values)
    values.pop(field)
    fixture.provider_file.write_text(json.dumps(values))
    requests = model(monkeypatch)
    assert invoke(capsys, command(fixture))[0] == 2 and not requests


def test_empty_abstention_is_completed_and_replayed_without_auto_retry(
    tmp_path, capsys, monkeypatch
):
    fixture = setup(tmp_path)
    requests = model(monkeypatch, proposals={"candidates": []})
    status, run = invoke(capsys, command(fixture))
    assert status == 0 and run["status"] == "completed" and run["items"] == []
    assert len(requests) == 1 and not fixture.store.entries()
    assert invoke(capsys, command(fixture))[1]["replayed"] and len(requests) == 1


def test_declared_temporal_fields_are_parsed_and_preserved_in_pending_events(
    tmp_path, capsys, monkeypatch
):
    fixture = setup(tmp_path)
    requests = model(
        monkeypatch,
        proposals={
            "candidates": [{"kind": "event", "key": "event.observation", "quote": TEXT}],
        },
    )
    args = command(fixture) + [
        "--valid-from",
        "2026-09-01T00:00:00Z",
        "--valid-until",
        "2026-11-01T00:00:00Z",
        "--occurred-at",
        "2026-10-01T10:00:00-04:00",
    ]
    assert invoke(capsys, args)[0] == 0 and len(requests) == 1
    record = fixture.store.entries()[0]
    assert record["status"] == "pending"
    assert record["valid_from"] == "2026-09-01T00:00:00+00:00"
    assert record["valid_until"] == "2026-11-01T00:00:00+00:00"
    assert record["occurred_at"] == "2026-10-01T14:00:00+00:00"
    # Qualifiers stay server-side, rather than entering the model's source body.
    assert "2026-" not in requests[0].content.decode()


@pytest.mark.parametrize(
    "flags",
    [
        ["--occurred-at", "2026-10-01T10:00:00"],
        ["--valid-from", "2026-11-01T00:00:00Z", "--valid-until", "2026-10-01T00:00:00Z"],
    ],
)
def test_invalid_temporal_fields_prevent_delivery(tmp_path, capsys, monkeypatch, flags):
    fixture = setup(tmp_path)
    requests = model(monkeypatch)
    assert invoke(capsys, command(fixture) + flags)[0] == 2 and not requests


@pytest.mark.parametrize(
    "change",
    [
        "digest",
        "target",
        "source_revision",
        "policy_revision",
        "revoke",
        "policy",
        "content",
        "budget",
    ],
)
def test_stale_or_missing_authority_and_whole_source_budget_prevent_delivery(
    tmp_path, capsys, monkeypatch, change
):
    fixture = setup(tmp_path)
    args = command(fixture)
    if change in {"digest", "target"}:
        flag = "--reviewed-content-hash" if change == "digest" else "--reviewed-target-id"
        args[args.index(flag) + 1] = "0" * 64
    elif change in {"source_revision", "policy_revision"}:
        flag = (
            "--expected-source-revision"
            if change == "source_revision"
            else "--expected-disclosure-revision"
        )
        args[args.index(flag) + 1] = "1"
    elif change == "revoke":
        fixture.pipeline.approve(fixture.source["id"], approved=False, expected_revision=2)
    elif change == "policy":
        fixture.manager.configure(DisclosurePolicy(), 2)
        args[args.index("--expected-disclosure-revision") + 1] = "3"
    elif change == "content":
        fixture.content_file.write_text(TEXT + " Changed draft.", encoding="utf-8")
    else:
        fixture.provider_file.write_text(
            json.dumps({**fixture.values, "max_context_chars": len(INSTRUCTIONS)})
        )
        status, review = invoke(capsys, command(fixture, "review"))
        assert status == 0 and review["max_source_chars"] == 0 and not review["source_fits_budget"]
    requests = model(monkeypatch)
    assert invoke(capsys, args)[0] == 2
    assert not requests and not fixture.store.entries() and not fixture.pipeline.runs()


def test_sensitive_opt_in_is_separate_from_provider_consent(tmp_path, capsys, monkeypatch):
    fixture = setup(tmp_path, sensitivity="sensitive")
    requests = model(monkeypatch)
    assert invoke(capsys, command(fixture, "review"))[1]["sensitivity"] == "sensitive"
    assert invoke(capsys, command(fixture))[0] == 2 and not requests
    assert invoke(capsys, command(fixture) + ["--allow-sensitive"])[0] == 0 and len(requests) == 1
    assert all(row["sensitivity"] == "sensitive" for row in fixture.store.entries())


def test_revocation_during_delivery_blocks_storage_without_holding_write_lock(
    tmp_path, capsys, monkeypatch
):
    fixture = setup(tmp_path)
    requests = model(
        monkeypatch,
        callback=lambda _: fixture.pipeline.approve(
            fixture.source["id"], approved=False, expected_revision=2
        ),
    )
    assert invoke(capsys, command(fixture))[0] == 2
    assert len(requests) == 1 and not fixture.store.entries() and not fixture.pipeline.runs()


def test_invalid_batch_has_exit_one_and_explicit_retry_preserves_run_id(
    tmp_path, capsys, monkeypatch
):
    fixture = setup(tmp_path)
    requests = model(
        monkeypatch,
        proposals={
            "candidates": [
                *PROPOSALS["candidates"],
                {"kind": "fact", "key": "invented", "quote": "Not present"},
            ]
        },
    )
    status, run = invoke(capsys, command(fixture))
    assert status == 1 and run["error_code"] == "extraction_invalid" and not fixture.store.entries()
    assert run["items"] == [] and len(requests) == 1
    requests = model(monkeypatch)
    status, retry = invoke(capsys, command(fixture))
    assert (
        status == 0 and retry["id"] == run["id"] and retry["attempts"] == 2 and len(requests) == 1
    )


@pytest.mark.parametrize(
    "kind,code",
    [
        ("status", "provider_request_failed"),
        ("timeout", "provider_timeout"),
        ("envelope", "provider_response_invalid"),
        ("oversized", "provider_response_too_large"),
    ],
)
def test_provider_failures_are_classified_without_traceback_secret_or_response(
    tmp_path, capsys, monkeypatch, kind, code
):
    fixture = setup(tmp_path)

    def response(request):
        if kind == "timeout":
            raise httpx.ReadTimeout(KEY + " PrivateProviderErrorMarker", request=request)
        if kind == "status":
            return httpx.Response(500, text=KEY + " PrivateProviderErrorMarker")
        if kind == "oversized":
            return httpx.Response(200, headers={"content-length": "50000001"}, content=b"")
        return httpx.Response(200, json={"secret": KEY, "message": "PrivateProviderErrorMarker"})

    requests = model(monkeypatch, response=response)
    status, error = invoke(capsys, command(fixture))
    assert status == 2 and error == {"error": code} and len(requests) == 1
    assert not fixture.store.entries() and not fixture.pipeline.runs()
    audit = json.dumps(AuditLog(fixture.store).events())
    assert "PrivateProviderErrorMarker" not in audit and KEY not in audit


@pytest.mark.parametrize(
    "update",
    [
        {"llm_api_key": ""},
        {"llm_api_key": "secret\nHeader"},
        {"llm_api_key": 123},
        {"llm_api_key": "秘密"},
        {"llm_model": " "},
        {"llm_model": "\ud800"},
        {"llm_base_url": "file:///tmp/provider"},
        {"llm_base_url": "http://name:key@fixture.invalid"},
        {"llm_base_url": "https://fixture.invalid/v1?key=private"},
        {"llm_base_url": "https://fixture.invalid/#fragment"},
        {"llm_base_url": "https://fixture.invalid:999999"},
        {"max_context_chars": True},
        {"max_context_chars": 100001},
        {"provider_timeout_seconds": 0},
        {"personal_token": "hidden"},
    ],
)
def test_explicit_config_rejects_invalid_unknown_and_coerced_fields_without_delivery(
    tmp_path, capsys, monkeypatch, update
):
    fixture = setup(tmp_path)
    fixture.provider_file.write_text(json.dumps({**fixture.values, **update}), encoding="utf-8")
    requests = model(monkeypatch)
    status, error = invoke(capsys, command(fixture))
    assert status == 2 and error == {"error": "Invalid command data"} and not requests
    assert not fixture.store.entries()


@pytest.mark.parametrize("invalid", ["duplicate", "malformed", "oversize", "directory", "missing"])
def test_config_file_read_is_bounded_and_json_is_unambiguous(
    tmp_path, capsys, monkeypatch, invalid
):
    fixture = setup(tmp_path)
    if invalid == "duplicate":
        fixture.provider_file.write_text('{"llm_api_key":"' + KEY + '","llm_api_key":"second"}')
    elif invalid == "malformed":
        fixture.provider_file.write_text(KEY + " malformed")
    elif invalid == "oversize":
        fixture.provider_file.write_bytes(b" " * (MAX_CONFIG_BYTES + 1))
    elif invalid == "directory":
        fixture.provider_file.unlink()
        fixture.provider_file.mkdir()
    else:
        fixture.provider_file.unlink()
    requests = model(monkeypatch)
    assert invoke(capsys, command(fixture))[0] == 2 and not requests


@pytest.mark.parametrize(
    "content",
    [b"\xffPRIVATE_INPUT", b"a" * 80001, "林".encode() * 66667, b""],
    ids=["invalid-utf8", "too-many-codepoints", "too-many-bytes", "empty"],
)
def test_source_invalid_unicode_character_and_byte_limits_never_send(
    tmp_path, capsys, monkeypatch, content
):
    fixture = setup(tmp_path)
    fixture.content_file.write_bytes(content)
    requests = model(monkeypatch)
    status, error = invoke(capsys, command(fixture))
    assert status == 2 and "PRIVATE_INPUT" not in json.dumps(error) and not requests


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="Named pipes are unavailable on Windows")
def test_source_named_pipe_is_rejected_without_waiting_for_a_writer(tmp_path, capsys):
    fixture = setup(tmp_path)
    fixture.content_file.unlink()
    os.mkfifo(fixture.content_file)
    assert invoke(capsys, command(fixture, "review"))[0] == 2


def test_real_subprocess_cli_loopback_model_and_provider_free_baseline(tmp_path):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(
                (self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            )
            body = json.dumps(
                {"choices": [{"message": {"content": json.dumps(PROPOSALS)}}]}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        fixture = setup(tmp_path, base_url=f"http://127.0.0.1:{server.server_port}/v1")
        environment = {
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
            "LLM_API_KEY": "unrelated-ambient-key",
            "MAX_CONTEXT_CHARS": "1",
        }
        environment.pop("PYTHONSTARTUP", None)

        def run(args):
            result = subprocess.run(
                [sys.executable, "-m", "app.agent_cli", *args],
                cwd=tmp_path,
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
            )
            assert KEY not in result.stdout + result.stderr
            assert "Traceback" not in result.stderr
            return result

        (tmp_path / ".env").write_text("LLM_BASE_URL=http://must-not-be-used.invalid/v1\n")
        assert run(command(fixture, "review")).returncode == 0 and not requests
        result = run(command(fixture))
        assert result.returncode == 0 and json.loads(result.stdout)["status"] == "completed"
        assert len(requests) == 1 and requests[0][0] == "/v1/chat/completions"
        assert requests[0][1]["messages"][1]["content"] == TEXT
        assert run(command(fixture)).returncode == 0 and len(requests) == 1
        result = run(["--data-dir", str(fixture.store.root), "ask", "What is my name?"])
        assert result.returncode == 0 and len(requests) == 1
        assert fixture.store.entries()[0]["status"] == "pending"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
