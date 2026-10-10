from pathlib import Path

import httpx
import pytest

from app.config import Settings, get_settings
from app.main import app
from app.memory import Entry, MemoryConflict, MemoryNotFound, Store


@pytest.fixture
async def personal(tmp_path):
    knowledge = tmp_path / "public"
    knowledge.mkdir()
    config = Settings(
        _env_file=None,
        personal_enabled=True,
        personal_token="t" * 40,
        personal_data_dir=str(tmp_path / "private"),
        knowledge_dir=str(knowledge),
    )
    app.dependency_overrides[get_settings] = lambda: config
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, config
    app.dependency_overrides.clear()


HEADERS = {"Authorization": "Bearer " + "t" * 40}


async def test_auth_and_disabled(personal):
    client, config = personal
    for path in ("entries", "history", "export"):
        assert (await client.get(f"/api/v1/personal/{path}")).status_code == 401
    assert not Path(config.personal_data_dir).exists()  # noqa: ASYNC240
    config.personal_enabled = False
    assert (await client.get("/api/v1/personal/entries", headers=HEADERS)).status_code == 404


async def test_confirm_edit_delete_and_public_isolation(personal):
    client, config = personal
    base = "/api/v1/personal"
    response = await client.post(
        base + "/entries",
        headers=HEADERS,
        json={"kind": "fact", "key": "project", "content": "SecretOrchid"},
    )
    item = response.json()
    assert item["status"] == "pending"
    query = {"question": "SecretOrchid"}
    assert not (await client.post(base + "/chat", json=query, headers=HEADERS)).json()["sources"]
    await client.post(base + f"/entries/{item['id']}/confirm", headers=HEADERS, json={})
    assert (
        "SecretOrchid"
        in (await client.post(base + "/chat", json=query, headers=HEADERS)).json()["answer"]
    )
    assert not (await client.post("/api/v1/chat", json=query)).json()["sources"]
    # A new Store instance sees persisted confirmed data.
    assert Store(config.personal_data_dir).entries()[0]["status"] == "confirmed"
    await client.post(
        base + f"/entries/{item['id']}/edit",
        headers=HEADERS,
        json={"kind": "fact", "key": "project", "content": "NewOrchid"},
    )
    assert not (await client.post(base + "/chat", json=query, headers=HEADERS)).json()["sources"]
    await client.post(base + f"/entries/{item['id']}/confirm", headers=HEADERS, json={})
    await client.post(base + f"/entries/{item['id']}/delete", headers=HEADERS, json={})
    assert not (await client.post(base + "/chat", json=query, headers=HEADERS)).json()["sources"]
    exported = (await client.get(base + "/export", headers=HEADERS)).json()
    assert exported["entries"] == [] and exported["history"]
    await client.post(base + "/history/clear", headers=HEADERS, json={})
    assert (await client.get(base + "/history", headers=HEADERS)).json() == []


async def test_candidate_and_explicit_conflict(personal):
    client, _ = personal
    base = "/api/v1/personal"
    await client.post(base + "/chat", headers=HEADERS, json={"question": "记住：先给结论"})
    items = (await client.get(base + "/entries", headers=HEADERS)).json()
    first = items[0]
    assert first["content"] == "先给结论" and first["source"].startswith("turn:")
    await client.post(base + f"/entries/{first['id']}/confirm", headers=HEADERS, json={})
    await client.post(base + "/chat", headers=HEADERS, json={"question": "记住：先给细节"})
    second = (await client.get(base + "/entries", headers=HEADERS)).json()[1]
    url = base + f"/entries/{second['id']}/confirm"
    assert (await client.post(url, headers=HEADERS, json={})).status_code == 409
    assert (
        await client.post(url, headers=HEADERS, json={"replace_ids": ["wrong"]})
    ).status_code == 409
    assert (
        await client.post(url, headers=HEADERS, json={"replace_ids": [first["id"]]})
    ).status_code == 200
    assert len((await client.get(base + "/entries", headers=HEADERS)).json()) == 1
    memories = (await client.get(base + "/entries?include_superseded=true", headers=HEADERS)).json()
    assert [item["status"] for item in memories] == ["superseded", "confirmed"]
    assert memories[0]["superseded_by"] == second["id"]


async def test_private_markdown_and_validation(personal):
    client, config = personal
    root = Path(config.personal_data_dir) / "knowledge"
    root.mkdir(parents=True)
    (root / "local.md").write_text("# Private\n\nSecretTulip", encoding="utf-8")
    result = await client.post(
        "/api/v1/personal/chat", headers=HEADERS, json={"question": "SecretTulip"}
    )
    assert result.json()["sources"][0]["path"].startswith("private/knowledge/")
    assert not (await client.post("/api/v1/chat", json={"question": "SecretTulip"})).json()[
        "sources"
    ]
    assert (
        await client.post(
            "/api/v1/personal/entries", headers=HEADERS, json={"key": " ", "content": "x"}
        )
    ).status_code == 422


def test_preferences_survive_and_deleted_not_retrieved(tmp_path):
    db = Store(str(tmp_path))
    item = db.add(Entry(kind="preference", key="response.style", content="Be concise"))
    assert db.context("unrelated") == []
    db.confirm(item["id"], [])
    assert Store(str(tmp_path)).context("unrelated")
    db.delete(item["id"])
    assert not db.context("unrelated")


def test_confirmed_preference_not_evicted_by_many_matching_facts(tmp_path):
    db = Store(str(tmp_path))
    pref = db.add(Entry(kind="preference", key="response.style", content="Use bullets"))
    db.confirm(pref["id"], [])
    for number in range(20):
        fact = db.add(Entry(kind="fact", key=f"project{number}", content="orchid"))
        db.confirm(fact["id"], [])
    matches = db.context("orchid")
    assert any(m.document.path == f"memory/{pref['id']}" for m in matches), (
        f"confirmed preference was evicted from context: {[m.document.path for m in matches]}"
    )
    # 1 preference + 20 facts is one candidate over budget, so the total stays capped at 20.
    assert len(matches) == 20


def test_context_preferences_below_quota_are_never_dropped(tmp_path):
    db = Store(str(tmp_path))
    prefs = []
    for number in range(8):
        pref = db.add(Entry(kind="preference", key=f"pref{number}", content="Be concise"))
        db.confirm(pref["id"], [])
        prefs.append(pref)
    matches = db.context("unrelated")
    assert {m.document.path for m in matches} == {f"memory/{p['id']}" for p in prefs}


def test_context_ranks_relevant_facts_above_less_relevant_preference(tmp_path):
    db = Store(str(tmp_path))
    fact = db.add(Entry(kind="fact", key="topic", content="orchid bloom"))
    db.confirm(fact["id"], [])
    pref = db.add(Entry(kind="preference", key="response.style", content="orchid"))
    db.confirm(pref["id"], [])
    matches = db.context("orchid bloom")
    assert [m.document.path for m in matches] == [f"memory/{fact['id']}", f"memory/{pref['id']}"]


def test_context_drops_lowest_scoring_preferences_once_budget_is_exceeded(tmp_path):
    db = Store(str(tmp_path))
    tokens = [f"tok{n}" for n in range(10)]
    query = " ".join(tokens)
    preferences = []
    for number, prefix_len in enumerate(range(1, 11)):
        content = " ".join(tokens[:prefix_len])
        pref = db.add(Entry(kind="preference", key=f"pref{number}", content=content))
        db.confirm(pref["id"], [])
        preferences.append(pref)
    facts = []
    for number in range(15):
        fact = db.add(Entry(kind="fact", key=f"fact{number}", content=query))
        db.confirm(fact["id"], [])
        facts.append(fact)
    matches = db.context(query)
    paths = {m.document.path for m in matches}
    assert len(matches) == 20
    assert paths == {f"memory/{f['id']}" for f in facts} | {
        f"memory/{p['id']}" for p in preferences[5:]
    }


async def test_private_provider_receives_only_current_confirmed_context(personal, monkeypatch):
    import app.personal as personal_module

    client, config = personal
    captured = []

    async def fake_answer(**kwargs):
        captured.append(kwargs)
        return "Generated answer", "openai-compatible"

    monkeypatch.setattr(personal_module, "generate_answer", fake_answer)
    db = Store(config.personal_data_dir)
    pending = db.add(Entry(kind="fact", key="private.fact", content="PendingSecret"))
    approved = db.add(Entry(kind="preference", key="response.style", content="Short paragraphs"))
    db.confirm(approved["id"], [])
    db.save_chat("OldSecret", "Old answer")
    response = await client.post(
        "/api/v1/personal/chat", headers=HEADERS, json={"question": "PendingSecret"}
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    context = "\n".join(m.excerpt for m in captured[0]["matches"])
    assert "Short paragraphs" in context
    assert "PendingSecret" not in context
    assert "OldSecret" not in context
    assert captured[0]["history"] == []
    db.delete(pending["id"])
    db.delete(approved["id"])
    await client.post("/api/v1/personal/chat", headers=HEADERS, json={"question": "paragraphs"})
    assert not captured[-1]["matches"]


@pytest.mark.parametrize(
    "payload",
    [
        {"replace_ids": [], "status": "confirmed"},
        {"replace_ids": ["same", "same"]},
        {"replace_ids": [""]},
        {"replace_ids": [" "]},
        {"replace_ids": [123]},
        {"replace_ids": ["x" * 101]},
        {"replace_ids": [str(i) for i in range(101)]},
    ],
)
async def test_confirmation_rejects_malformed_contract(personal, payload):
    client, config = personal
    db = Store(config.personal_data_dir)
    item = db.add(Entry(key="project", content="Example"))
    response = await client.post(
        f"/api/v1/personal/entries/{item['id']}/confirm", headers=HEADERS, json=payload
    )
    assert response.status_code == 422
    assert db.entries()[0]["status"] == "pending"


async def test_typed_memory_export_and_provenance(personal):
    from app.personal import MemoryExport, MemoryRecord

    client, config = personal
    db = Store(config.personal_data_dir)
    db.save_chat("Remember: Use concise answers", "Noted")
    response = await client.get("/api/v1/personal/export", headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    exported = MemoryExport.model_validate(response.json())
    memory = exported.entries[0]
    assert memory.source == f"turn:{exported.history[0].id}"
    assert memory.created_at.tzinfo is not None
    assert memory.updated_at == memory.created_at
    listed = await client.get("/api/v1/personal/entries", headers=HEADERS)
    assert MemoryRecord.model_validate(listed.json()[0]) == memory
    schema = app.openapi()
    assert "MemoryRecord" in schema["components"]["schemas"]
    assert "MemoryExport" in schema["components"]["schemas"]


def test_export_uses_one_snapshot_during_concurrent_deletion(tmp_path, monkeypatch):
    import sqlite3
    from contextlib import contextmanager

    db = Store(str(tmp_path))
    db.add(Entry(key="project", content="Example"))
    db.save_chat("Example question", "Example answer")
    with db.connect() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
    original_connect = db.connect

    class ConcurrentWriter:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, query):
            if query == "SELECT * FROM turns ORDER BY rowid":
                # A writer commits between the two export SELECTs.
                with sqlite3.connect(db.path) as writer:
                    writer.execute("DELETE FROM revisions")
                    writer.execute("DELETE FROM entries")
                    writer.execute("DELETE FROM turns")
            return self.connection.execute(query)

    @contextmanager
    def interleaved_connect():
        with original_connect() as connection:
            yield ConcurrentWriter(connection)

    monkeypatch.setattr(db, "connect", interleaved_connect)
    exported = db.export()
    assert len(exported["entries"]) == 1
    assert len(exported["history"]) == 2
    assert len(exported["revisions"]) == 1
    with original_connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM turns").fetchone()[0] == 0


def test_memory_revision_lifecycle_and_provenance(tmp_path):
    db = Store(str(tmp_path))
    original = db.add(Entry(key="project", content="OldOrchid"), source="turn:example")
    db.confirm(original["id"], [], expected_revision=1)
    db.edit(original["id"], Entry(key="project", content="NewOrchid"), expected_revision=2)
    assert not db.context("OldOrchid")
    assert not db.context("NewOrchid")  # Corrected content still needs review.
    revisions = db.revisions(original["id"])
    assert [item["change"] for item in revisions] == ["created", "confirmed", "edited"]
    assert [item["revision"] for item in revisions] == [1, 2, 3]
    assert [item["source"] for item in revisions] == ["turn:example", "turn:example", "manual"]
    assert [item["content"] for item in revisions] == ["OldOrchid", "OldOrchid", "NewOrchid"]
    assert len({item["created_at"] for item in revisions}) == 1
    db.confirm(original["id"], [], expected_revision=3)
    db.confirm(original["id"], [])  # Replay without a version precondition is idempotent.
    assert len(db.revisions(original["id"])) == 4
    assert db.context("NewOrchid")[0].excerpt == "project: NewOrchid"
    assert Store(str(tmp_path)).revisions(original["id"]) == db.revisions(original["id"])


def test_supersession_never_resurrects_and_deletion_purges_revisions(tmp_path):
    db = Store(str(tmp_path))
    old = db.add(Entry(kind="preference", key="style", content="OldOrchid"))
    db.confirm(old["id"], [])
    current = db.add(Entry(kind="preference", key="style", content="NewOrchid"))
    db.confirm(current["id"], [old["id"]], 1, {old["id"]: 2})
    archived = db.revisions(old["id"])[-1]
    assert archived["status"] == "superseded"
    assert archived["change"] == "superseded"
    assert archived["superseded_by"] == current["id"]
    assert all("OldOrchid" not in match.excerpt for match in db.context("OldOrchid"))
    for operation in (
        lambda: db.confirm(old["id"], [current["id"]]),
        lambda: db.edit(old["id"], Entry(key="other", content="Revive")),
    ):
        with pytest.raises((MemoryConflict, MemoryNotFound)) as error:
            operation()
        assert isinstance(error.value, MemoryConflict)
    db.delete(current["id"])
    assert not db.context("OldOrchid")  # Removing the replacement cannot reactivate history.
    assert {r["id"] for r in db.export()["revisions"]} == {old["id"]}
    db.delete(old["id"])
    assert db.export()["entries"] == []
    assert db.export()["revisions"] == []
    with pytest.raises((MemoryConflict, MemoryNotFound)) as error:
        db.revisions(old["id"])
    assert isinstance(error.value, MemoryNotFound)


def test_legacy_workspace_migrates_once_without_inventing_history(tmp_path):
    import sqlite3

    timestamp = "2026-01-01T00:00:00+00:00"
    with sqlite3.connect(tmp_path / "twin.sqlite3") as db:
        db.execute(
            "CREATE TABLE entries (id TEXT PRIMARY KEY, kind TEXT, key TEXT, content TEXT, "
            "source TEXT, status TEXT, created_at TEXT, updated_at TEXT)"
        )
        db.execute(
            "INSERT INTO entries VALUES (?,?,?,?,?,?,?,?)",
            (
                "legacy",
                "fact",
                "project",
                "LegacyOrchid",
                "manual",
                "confirmed",
                timestamp,
                timestamp,
            ),
        )
        db.execute("CREATE TABLE turns (id TEXT, role TEXT, content TEXT, created_at TEXT)")
        db.execute("INSERT INTO turns VALUES ('turn', 'user', 'Question', ?)", (timestamp,))
    db = Store(str(tmp_path))
    migrated = db.entries()[0]
    assert migrated["content"] == "LegacyOrchid"
    assert migrated["status"] == "confirmed"
    assert migrated["created_at"] == migrated["updated_at"] == timestamp
    assert migrated["revision"] == 1 and migrated["superseded_by"] is None
    assert db.revisions("legacy") == [{**migrated, "change": "baseline"}]
    assert db.history()[0]["content"] == "Question"
    assert db.context("LegacyOrchid")
    db.edit("legacy", Entry(key="project", content="CurrentOrchid"), 1)
    reopened = Store(str(tmp_path))
    assert [r["change"] for r in reopened.revisions("legacy")] == ["baseline", "edited"]
    assert reopened.export()["version"] == 2


def test_revision_writes_roll_back_with_failed_supersession(tmp_path, monkeypatch):
    db = Store(str(tmp_path))
    old = db.add(Entry(key="project", content="OldOrchid"))
    db.confirm(old["id"], [])
    current = db.add(Entry(key="project", content="NewOrchid"))
    before = db.export()
    original = db._snapshot

    def fail_after_archive(connection, entry_id, change):
        if change == "confirmed":
            raise RuntimeError("Synthetic storage failure")
        original(connection, entry_id, change)

    monkeypatch.setattr(db, "_snapshot", fail_after_archive)
    with pytest.raises(RuntimeError, match="Synthetic"):
        db.confirm(current["id"], [old["id"]])
    assert db.export() == before


async def test_version_preconditions_reject_stale_review_without_mutation(personal):
    client, config = personal
    db = Store(config.personal_data_dir)
    item = db.add(Entry(key="project", content="OriginalOrchid"))
    db.edit(item["id"], Entry(key="project", content="ChangedOrchid"), 1)
    before = db.export()
    for action, payload in (
        ("confirm", {"expected_revision": 1}),
        ("edit", {"expected_revision": 1, "key": "project", "content": "StaleOrchid"}),
    ):
        result = await client.post(
            f"/api/v1/personal/entries/{item['id']}/{action}", headers=HEADERS, json=payload
        )
        assert result.status_code == 409
        assert "refresh" in result.json()["detail"]
    assert db.export() == before
    db.confirm(item["id"], [], 2)
    replacement = db.add(Entry(key="project", content="ReplacementOrchid"))
    endpoint = f"/api/v1/personal/entries/{replacement['id']}/confirm"
    conflict = (await client.post(endpoint, headers=HEADERS, json={})).json()["detail"]
    assert conflict["conflict_revisions"] == {item["id"]: 3}
    db.edit(item["id"], Entry(key="project", content="ConcurrentOrchid"), 3)
    db.confirm(item["id"], [], 4)
    before = db.export()
    result = await client.post(
        endpoint,
        headers=HEADERS,
        json={
            "expected_revision": 1,
            "replace_ids": [item["id"]],
            "replace_revisions": {item["id"]: 3},
        },
    )
    assert result.status_code == 409
    assert db.export() == before


async def test_revision_route_auth_export_and_delete(personal):
    client, config = personal
    db = Store(config.personal_data_dir)
    item = db.add(Entry(key="project", content="PrivateOrchid"))
    endpoint = f"/api/v1/personal/entries/{item['id']}/history"
    assert (await client.get(endpoint)).status_code == 401
    response = await client.get(endpoint, headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()[0]["change"] == "created"
    exported = (await client.get("/api/v1/personal/export", headers=HEADERS)).json()
    assert exported["version"] == 2
    assert exported["revisions"] == response.json()
    await client.post(f"/api/v1/personal/entries/{item['id']}/delete", headers=HEADERS)
    assert (await client.get(endpoint, headers=HEADERS)).status_code == 404
    assert (await client.get("/api/v1/personal/export", headers=HEADERS)).json()["revisions"] == []


@pytest.mark.parametrize("version", [0, -1, True, 1.2, "2"])
async def test_invalid_revision_preconditions(personal, version):
    client, _ = personal
    for action, payload in (
        ("confirm", {"expected_revision": version}),
        ("edit", {"expected_revision": version, "key": "project", "content": "Orchid"}),
        ("confirm", {"replace_revisions": {"other": version}}),
    ):
        result = await client.post(
            f"/api/v1/personal/entries/missing/{action}", headers=HEADERS, json=payload
        )
        assert result.status_code == 422


def test_concurrent_edits_with_version_gate_only_commit_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    db = Store(str(tmp_path))
    item = db.add(Entry(key="project", content="OriginalOrchid"))

    def edit(content):
        try:
            db.edit(item["id"], Entry(key="project", content=content), 1)
            return 200
        except MemoryConflict:
            return 409

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit, ["OneOrchid", "TwoOrchid"])) == [200, 409]
    assert len(db.revisions(item["id"])) == 2


async def test_restore_is_a_source_linked_pending_proposal(personal):
    client, config = personal
    db = Store(config.personal_data_dir)
    original = db.add(Entry(key="project", content="OriginalOrchid"))
    db.confirm(original["id"], [])
    db.edit(original["id"], Entry(key="project", content="CurrentOrchid"), 2)
    db.confirm(original["id"], [], 3)
    before = db.revisions(original["id"])
    path = f"/api/v1/personal/entries/{original['id']}/restore"
    assert (await client.post(path, json={"revision": 2})).status_code == 401
    assert (
        await client.post(path, headers=HEADERS, json={"revision": 2, "expected_revision": 3})
    ).status_code == 409
    assert (
        await client.post(path, headers=HEADERS, json={"revision": 100, "expected_revision": 4})
    ).status_code == 404
    restored = (
        await client.post(path, headers=HEADERS, json={"revision": 2, "expected_revision": 4})
    ).json()
    assert restored["id"] != original["id"]
    assert restored["content"] == "OriginalOrchid"
    assert restored["source"] == f"memory:{original['id']}@2"
    assert restored["status"] == "pending" and restored["revision"] == 1
    assert db.revisions(original["id"]) == before
    assert not db.context("OriginalOrchid")
    db.confirm(restored["id"], [original["id"]], 1, {original["id"]: 4})
    assert db.context("OriginalOrchid")[0].document.path == f"memory/{restored['id']}"
    # Restoration from an archived source is also pending and leaves archives read-only.
    again = db.restore(original["id"], 1, expected_revision=5)
    assert again["status"] == "pending"
    assert db.entries(include_superseded=True)[0]["status"] == "superseded"


@pytest.mark.parametrize(
    "payload",
    [
        {"revision": 0},
        {"revision": True},
        {"revision": "1"},
        {"revision": 1, "status": "confirmed"},
    ],
)
async def test_restore_rejects_invalid_contract(personal, payload):
    client, _ = personal
    result = await client.post(
        "/api/v1/personal/entries/missing/restore", headers=HEADERS, json=payload
    )
    assert result.status_code == 422


def test_chat_and_candidate_are_atomic_and_normal_chat_does_not_ingest(tmp_path, monkeypatch):
    db = Store(str(tmp_path))
    db.save_chat("I prefer concise answers", "Synthetic answer")
    assert not db.entries() and not db.export()["revisions"]
    before = db.export()

    def fail(*_args):
        raise RuntimeError("Synthetic snapshot failure")

    monkeypatch.setattr(db, "_snapshot", fail)
    with pytest.raises(RuntimeError, match="snapshot failure"):
        db.save_chat("Remember: Be concise", "Synthetic answer")
    assert db.export() == before


def test_memory_core_does_not_depend_on_web_server(tmp_path):
    import subprocess
    import sys

    code = (
        "import sys; from app.memory import Entry, Store; "
        "db=Store(sys.argv[1]); "
        "item=db.add(Entry(key='project', content='SyntheticOrchid')); "
        "db.confirm(item['id'], []); "
        "assert db.context('SyntheticOrchid'); "
        "assert 'fastapi' not in sys.modules; "
        "assert 'httpx' not in sys.modules; "
        "assert 'app.provider' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_native_review_contract_rejects_malformed_input_before_mutation(tmp_path):
    from pydantic import ValidationError

    db = Store(str(tmp_path))
    item = db.add(Entry(key="project", content="SyntheticOrchid"))
    before = db.export()
    actions = (
        lambda: db.confirm(item["id"], ["same", "same"]),
        lambda: db.confirm(item["id"], [], True),
        lambda: db.confirm(item["id"], [], 1, {"other": True}),
        lambda: db.edit(item["id"], Entry(key="project", content="ChangedOrchid"), 0),
        lambda: db.restore(item["id"], True),
        lambda: db.restore(item["id"], 1, False),
    )
    for action in actions:
        with pytest.raises(ValidationError):
            action()
        assert db.export() == before


def test_concurrent_initialization_migrates_once_and_rejects_future_schema(tmp_path):
    import sqlite3
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=4) as pool:
        stores = list(pool.map(lambda _: Store(str(tmp_path)), range(4)))
    item = stores[0].add(Entry(key="project", content="SyntheticOrchid"))
    assert len(stores[-1].revisions(item["id"])) == 1
    with sqlite3.connect(stores[0].path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        connection.execute("PRAGMA user_version=3")
    with pytest.raises(ValueError, match="newer"):
        Store(str(tmp_path))
    with sqlite3.connect(stores[0].path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 1


async def test_superseded_versions_never_reach_provider_or_public_routes(personal, monkeypatch):
    import app.personal as personal_module

    client, config = personal
    captured = []

    async def fake_answer(**kwargs):
        captured.extend(m.excerpt for m in kwargs["matches"])
        return "Synthetic answer", "openai-compatible"

    monkeypatch.setattr(personal_module, "generate_answer", fake_answer)
    db = Store(config.personal_data_dir)
    original = db.add(Entry(kind="preference", key="style", content="SupersededOrchid"))
    db.confirm(original["id"], [])
    current = db.add(Entry(kind="preference", key="style", content="CurrentOrchid"))
    db.confirm(current["id"], [original["id"]])
    response = await client.post(
        "/api/v1/personal/chat", headers=HEADERS, json={"question": "SupersededOrchid"}
    )
    assert response.status_code == 200
    assert captured == ["style: CurrentOrchid"]
    assert all("SupersededOrchid" not in source["excerpt"] for source in response.json()["sources"])
    public = await client.post("/api/v1/chat", json={"question": "CurrentOrchid"})
    assert public.json()["sources"] == []
