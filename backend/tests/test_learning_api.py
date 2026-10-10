import pytest

from app.memory import Entry, Store
from app.memory_models import MemoryExport

HEADERS = {"Authorization": "Bearer " + "t" * 40}
BASE = "/api/v1/personal"


async def test_learning_api_auth_approval_ingestion_origins_and_export(personal):
    client, config = personal
    for path in ("/learning/sources", "/learning/runs", "/entries/missing/origins"):
        response = await client.get(BASE + path)
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"
    response = await client.post(
        BASE + "/learning/sources",
        headers=HEADERS,
        json={"kind": "document", "name": "Synthetic profile"},
    )
    source = response.json()
    assert response.status_code == 200 and source["approved"] is False
    payload = {"content": "fact identity.name: Alex Example"}
    path = BASE + f"/learning/sources/{source['id']}"
    assert (await client.post(path + "/ingest", headers=HEADERS, json=payload)).status_code == 403
    assert (
        await client.post(
            path + "/review", headers=HEADERS, json={"approved": True, "expected_revision": 1}
        )
    ).status_code == 200
    response = await client.post(path + "/ingest", headers=HEADERS, json=payload)
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "completed"
    assert response.headers["cache-control"] == "no-store"
    entry_id = run["items"][0]["memory_id"]
    origins = (await client.get(BASE + f"/entries/{entry_id}/origins", headers=HEADERS)).json()
    assert origins[0]["excerpt"] == "Alex Example"
    assert (await client.get(BASE + "/learning/runs", headers=HEADERS)).json()[0] == run
    exported = (await client.get(BASE + "/export", headers=HEADERS)).json()
    assert MemoryExport.model_validate(exported).version == 8
    assert Store(config.personal_data_dir).entries()[0]["status"] == "pending"


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "document", "name": " "},
        {"kind": "url", "name": "Synthetic"},
        {"kind": "document", "name": "Synthetic", "approved": True},
        {"kind": "document", "name": "Synthetic", "id": "forged"},
        {"kind": "document", "name": "Synthetic", "sensitivity": "secret"},
    ],
)
async def test_learning_source_contract_rejects_client_state(personal, payload):
    client, _ = personal
    result = await client.post(BASE + "/learning/sources", headers=HEADERS, json=payload)
    assert result.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"approved": "true"},
        {"approved": True, "expected_revision": False},
        {"approved": True, "revision": 9},
    ],
)
async def test_learning_review_contract_is_strict(personal, payload):
    client, _ = personal
    result = await client.post(
        BASE + "/learning/sources/missing/review", headers=HEADERS, json=payload
    )
    assert result.status_code == 422


async def test_sensitive_memory_never_reaches_provider_without_explicit_opt_in(
    personal, monkeypatch, configured_private_provider
):
    import app.personal as module

    client, config = personal
    db = Store(config.personal_data_dir)
    item = db.add(
        Entry(
            kind="preference",
            key="private.style",
            content="SensitiveOrchid",
            sensitivity="sensitive",
        )
    )
    db.confirm(item["id"], [])
    captured = []

    async def answer(**kwargs):
        captured.append([match.excerpt for match in kwargs["matches"]])
        return "Synthetic answer", "openai-compatible"

    monkeypatch.setattr(module, "generate_answer", answer)
    assert (
        await client.post(
            BASE + "/chat",
            headers=HEADERS,
            json={"question": "Synthetic query", "allow_provider": True},
        )
    ).status_code == 200
    assert captured[-1] == []
    assert (
        await client.post(
            BASE + "/chat",
            headers=HEADERS,
            json={"question": "Synthetic query", "allow_sensitive": True, "allow_provider": True},
        )
    ).status_code == 200
    assert captured[-1] == ["private.style: SensitiveOrchid"]
    assert (
        await client.post(
            BASE + "/chat",
            headers=HEADERS,
            json={"question": "Synthetic query", "allow_sensitive": "false"},
        )
    ).status_code == 422


async def test_ingestion_failure_response_is_inspectable_not_private_exception(personal):
    client, _ = personal
    source = (
        await client.post(
            BASE + "/learning/sources",
            headers=HEADERS,
            json={"kind": "document", "name": "Synthetic"},
        )
    ).json()
    path = BASE + f"/learning/sources/{source['id']}"
    await client.post(path + "/review", headers=HEADERS, json={"approved": True})
    response = await client.post(
        path + "/ingest", headers=HEADERS, json={"content": "malformed sensitive synthetic content"}
    )
    assert response.status_code == 200 and response.json()["status"] == "failed"
    assert response.json()["error_code"] == "extraction_invalid"
    assert "sensitive synthetic content" not in response.text


async def test_private_validation_is_unicode_safe_bounded_and_never_echoes_values(personal):
    client, _ = personal
    headers = {**HEADERS, "Content-Type": "application/json"}
    malformed = b'{"kind":"document","name":"private-synthetic-value-\\ud800"}'
    response = await client.post(BASE + "/learning/sources", headers=headers, content=malformed)
    assert response.status_code == 422
    assert "private-synthetic-value" not in response.text
    assert "input" not in response.json()["detail"][0]
    payload = {
        "kind": "document",
        "name": "Synthetic",
        **{f"extra{i}": "Private synthetic value" for i in range(30)},
    }
    response = await client.post(BASE + "/learning/sources", headers=HEADERS, json=payload)
    assert response.status_code == 422
    assert response.json()["errors_truncated"] is True
    assert len(response.json()["detail"]) == 20
    assert "Private synthetic value" not in response.text
    assert response.headers["cache-control"] == "no-store"
