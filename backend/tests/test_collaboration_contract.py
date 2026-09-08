"""Use the same public synthetic payloads as the browser's mocked-fetch tests."""

import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.main import collaborate
from app.schemas import CollaborationRequest, CollaborationResponse

FIXTURES = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "__fixtures__" / "collaboration"
)


@pytest.fixture(params=["baseline", "verified"])
def contract(request):
    return request.param, json.loads(
        (FIXTURES / f"{request.param}.json").read_text(encoding="utf-8")
    )


def test_shared_response_round_trips_without_shape_or_scalar_type_drift(contract) -> None:
    _, payload = contract
    response = CollaborationResponse.model_validate(payload)
    serialized = json.loads(response.model_dump_json())

    # Compare JSON too: Python equality alone considers True == 1 == 1.0.
    assert json.dumps(serialized, sort_keys=True) == json.dumps(payload, sort_keys=True)
    assert CollaborationResponse.model_validate_json(response.model_dump_json()) == response


async def test_route_serialization_matches_the_shared_contract(contract, tmp_path, monkeypatch):
    policy, payload = contract
    (tmp_path / "example.md").write_text(
        "# Example agent\n\nThe example agent plans projects from user goals.\n", encoding="utf-8"
    )
    monkeypatch.setattr("app.collaboration.uuid4", lambda: UUID(payload["run_id"][4:]))

    response = await collaborate(
        CollaborationRequest(question="How does the example agent plan projects?", workflow=policy),
        Settings(_env_file=None, knowledge_dir=str(tmp_path)),
    )

    assert json.dumps(json.loads(response.model_dump_json()), sort_keys=True) == json.dumps(
        payload, sort_keys=True
    )


def test_shared_response_rejects_an_unsupported_metric_value(contract) -> None:
    _, payload = contract
    payload["trace"][0]["metrics"]["task_count"] = {"unsupported": "nested object"}

    with pytest.raises(ValidationError, match="task_count"):
        CollaborationResponse.model_validate(payload)
