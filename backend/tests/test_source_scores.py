"""Keep normalized source scores consistent across public response models."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import ChatResponse, CollaborationResponse, Source

FIXTURES = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "__fixtures__" / "collaboration"
)


@pytest.fixture(params=["source", "chat", "baseline", "verified"])
def source_contract(request):
    fixture = "verified" if request.param == "verified" else "baseline"
    payload = json.loads((FIXTURES / f"{fixture}.json").read_text(encoding="utf-8"))
    source = payload["sources"][0]
    if request.param == "source":
        return Source, source, source
    if request.param == "chat":
        return (
            ChatResponse,
            {"answer": "Synthetic answer", "mode": "extractive", "sources": [source]},
            source,
        )
    return CollaborationResponse, payload, source


@pytest.mark.parametrize("score", [0.0, 0.5, 1.0])
def test_public_source_scores_accept_the_normalized_range(source_contract, score) -> None:
    model, payload, source = source_contract
    source["score"] = score

    response = model.model_validate(payload)
    validated_source = response if isinstance(response, Source) else response.sources[0]

    assert validated_source.score == score
    assert model.model_validate_json(response.model_dump_json()) == response


@pytest.mark.parametrize("score", [-0.25, 1.5, float("nan"), float("inf"), float("-inf")])
def test_public_source_scores_reject_out_of_range_and_nonfinite_values(
    source_contract, score
) -> None:
    model, payload, source = source_contract
    source["score"] = score

    with pytest.raises(ValidationError) as error:
        model.model_validate(payload)

    assert error.value.errors()[0]["loc"][-1] == "score"
