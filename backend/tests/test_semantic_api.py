import hashlib
import json

import pytest

from app.disclosure import learning_selector, target_id
from app.memory import Store

BASE = "/api/v1/personal"
H = {"Authorization": "Bearer " + "t" * 40}
TEXT = "My name is Alex Example."


async def fixture(client, config):
    config.llm_base_url = "https://provider.fixture.invalid/v1"
    config.llm_api_key = "fixture-key"
    config.llm_model = "fictional-model"
    source = (
        await client.post(
            BASE + "/learning/sources",
            headers=H,
            json={"kind": "document", "name": "Fictional input"},
        )
    ).json()
    source = (
        await client.post(
            BASE + f"/learning/sources/{source['id']}/review",
            headers=H,
            json={"approved": True, "expected_revision": 1},
        )
    ).json()
    target = target_id(config.llm_base_url, config.llm_model)
    response = await client.post(
        BASE + "/disclosure/policy",
        headers=H,
        json={
            "expected_revision": 1,
            "policy": {
                "enabled": True,
                "target_id": target,
                "namespaces": ["private"],
                "document_paths": [learning_selector(source["id"])],
            },
        },
    )
    assert response.status_code == 200
    return source, {
        "content": TEXT,
        "expected_source_revision": 2,
        "expected_disclosure_revision": 2,
        "reviewed_target_id": target,
        "reviewed_content_hash": hashlib.sha256(TEXT.encode()).hexdigest(),
    }


async def test_semantic_api_auth_review_consent_pending_provenance_and_replay(
    personal, monkeypatch
):
    from app import semantic_learning as module

    client, config = personal
    source, payload = await fixture(client, config)
    path = BASE + f"/learning/sources/{source['id']}"
    assert (await client.get(path + "/semantic-review")).status_code == 401
    review = await client.get(path + "/semantic-review", headers=H)
    assert review.status_code == 200 and review.headers["cache-control"] == "no-store"
    assert review.json()["selector"] == learning_selector(source["id"])
    assert review.json()["permitted"] and review.json()["configured"]
    assert "llm_api_key" not in review.text and config.llm_base_url not in review.text
    sent = []

    async def propose(settings, content, _transport=None):
        sent.append((settings.llm_model, content))
        return json.dumps(
            {"candidates": [{"kind": "fact", "key": "identity.name", "quote": "Alex Example"}]}
        )

    monkeypatch.setattr(module, "propose", propose)
    assert (
        await client.post(path + "/ingest-semantic", headers=H, json=payload)
    ).status_code == 403
    assert not sent
    response = await client.post(
        path + "/ingest-semantic", headers=H, json={**payload, "allow_provider": True}
    )
    assert response.status_code == 200 and response.json()["status"] == "completed"
    assert sent == [("fictional-model", TEXT)]
    db = Store(config.personal_data_dir)
    item = db.entries()[0]
    assert item["status"] == "pending" and item["content"] == "Alex Example"
    origin = (await client.get(BASE + f"/entries/{item['id']}/origins", headers=H)).json()[0]
    assert origin["excerpt"] == TEXT[origin["start"] : origin["end"]]
    again = await client.post(
        path + "/ingest-semantic", headers=H, json={**payload, "allow_provider": True}
    )
    assert again.json()["replayed"] and len(sent) == 1
    await client.post(
        BASE + f"/entries/{item['id']}/confirm",
        headers=H,
        json={"expected_revision": item["revision"]},
    )
    answer = await client.post(BASE + "/ask", headers=H, json={"question": "What is my name?"})
    assert answer.json()["status"] == "known"


@pytest.mark.parametrize(
    "extra",
    [
        {"allow_provider": "true"},
        {"expected_source_revision": True},
        {"expected_disclosure_revision": False},
        {"reviewed_content_hash": "wrong"},
        {"mode": "fields"},
        {"candidates": []},
        {"valid_from": "2030-01-01T00:00:00Z", "valid_until": "2020-01-01T00:00:00Z"},
    ],
)
async def test_semantic_api_strict_contract_and_no_private_input_echo(personal, extra):
    client, config = personal
    source, payload = await fixture(client, config)
    response = await client.post(
        BASE + f"/learning/sources/{source['id']}/ingest-semantic",
        headers=H,
        json={**payload, **extra},
    )
    assert response.status_code == 422 and TEXT not in response.text
    assert Store(config.personal_data_dir).entries() == []
