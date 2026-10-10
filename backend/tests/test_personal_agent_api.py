import pytest

from app.memory import Entry, Store
from app.retrieval_models import PersonalAnswer

H = {"Authorization": "Bearer " + "t" * 40}
BASE = "/api/v1/personal"


async def test_private_ask_retrieve_verify_contract_and_no_provider_call(personal, monkeypatch):
    import app.personal as module

    client, config = personal
    db = Store(config.personal_data_dir)
    item = db.add(Entry(key="identity.name", content="Alex Example"))
    db.confirm(item["id"], [])

    async def forbidden(**_kwargs):
        pytest.fail("Grounded local agent must not send data to the configured provider")

    monkeypatch.setattr(module, "generate_answer", forbidden)
    config.llm_base_url, config.llm_api_key, config.llm_model = (
        "https://example.invalid",
        "synthetic",
        "synthetic",
    )
    payload = {"question": "我的名字是什么"}
    assert (await client.post(BASE + "/ask", json=payload)).status_code == 401
    response = await client.post(BASE + "/ask", headers=H, json=payload)
    answer = PersonalAnswer.model_validate(response.json())
    assert answer.status == "known" and "Alex Example" in answer.answer
    assert response.headers["cache-control"] == "no-store"
    assert answer.mode == "personal-grounded-local"
    retrieved = await client.post(BASE + "/retrieve", headers=H, json=payload)
    assert retrieved.json()["evidence"][0]["id"] == answer.claims[0].claim.evidence_id
    verify = {"request": payload, "claims": [answer.claims[0].claim.model_dump()]}
    assert (await client.post(BASE + "/verify", headers=H, json=verify)).json()[0][
        "verdict"
    ] == "verified"
    db.delete(item["id"])
    assert (await client.post(BASE + "/verify", headers=H, json=verify)).json()[0][
        "verdict"
    ] == "unsupported"
    assert (await client.post(BASE + "/ask", headers=H, json=payload)).json()["status"] == "unknown"


async def test_explicit_owner_binding_and_sensitive_disclosure(personal):
    client, config = personal
    entity = (
        await client.post(
            BASE + "/identity/entities",
            headers=H,
            json={"kind": "person", "name": "Sensitive Example", "sensitivity": "sensitive"},
        )
    ).json()
    await client.post(
        BASE + f"/identity/entities/{entity['id']}/confirm",
        headers=H,
        json={"expected_revision": 1},
    )
    assert (
        await client.post(BASE + "/identity/owner", headers=H, json={"entity_id": entity["id"]})
    ).status_code == 200
    assert (await client.get(BASE + "/identity/owner", headers=H)).json()["entity_id"] == entity[
        "id"
    ]
    db = Store(config.personal_data_dir)
    item = db.add(Entry(key="identity.skills", content="PrivateOrchid", entity_id=entity["id"]))
    db.confirm(item["id"], [])
    payload = {"question": "What skills do I have?"}
    assert (await client.post(BASE + "/ask", headers=H, json=payload)).json()["status"] == "unknown"
    assert (
        await client.post(BASE + "/ask", headers=H, json={**payload, "allow_sensitive": True})
    ).json()["status"] == "known"


async def test_configured_question_context_limits_and_private_validation(personal):
    client, config = personal
    config.max_question_chars = 8
    assert (
        await client.post(BASE + "/ask", headers=H, json={"question": "x" * 9})
    ).status_code == 413
    config.max_question_chars = 8000
    config.max_context_chars = 10
    db = Store(config.personal_data_dir)
    item = db.add(Entry(key="identity.name", content="Alex Example"))
    db.confirm(item["id"], [])
    response = await client.post(BASE + "/ask", headers=H, json={"question": "What is my name?"})
    assert response.json()["context_chars"] <= 10 and response.json()["status"] == "unknown"
    invalid = await client.post(
        BASE + "/ask",
        headers=H,
        json={"question": "Private synthetic question", "allow_sensitive": "false"},
    )
    assert invalid.status_code == 422 and "Private synthetic question" not in invalid.text


async def test_public_documents_never_establish_the_owners_fictional_identity(personal):
    from pathlib import Path

    client, config = personal
    from starlette.concurrency import run_in_threadpool

    await run_in_threadpool(
        Path(config.knowledge_dir, "fiction.md").write_text,
        "# Fictional\n\nMy identity name is FictionalWrongOwner.",
        encoding="utf-8",
    )
    result = (
        await client.post(BASE + "/ask", headers=H, json={"question": "What is my name?"})
    ).json()
    assert result["status"] == "unknown" and "FictionalWrongOwner" not in result["answer"]
