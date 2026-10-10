#!/usr/bin/env python3
"""Offline exact-task semantic proposal scoring. No provider, private workspace or credential reads."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.memory import MemoryInputError
from app.memory_models import valid_unicode
from app.semantic_learning import _unique_pairs, literal_candidates
from app.semantic_models import SpanProposal

DEFAULT_DATASET = ROOT / "course" / "fixtures" / "semantic_cases.json"
MAX_JSON_BYTES = 1_048_576
SOURCE = {"sensitivity": "private", "entity_id": None}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TaskField(StrictModel):
    kind: Literal["fact", "preference", "event", "decision"]
    key: str = Field(min_length=1, max_length=100)
    _unicode = field_validator("key")(valid_unicode)


class BenchmarkCase(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    language: Literal["en", "zh", "mixed"]
    text: str = Field(min_length=1, max_length=80000)
    requested_fields: list[TaskField] = Field(min_length=1, max_length=20)
    expected: list[SpanProposal] = Field(max_length=100)
    annotation_note: str = Field(min_length=1, max_length=1000)
    _unicode = field_validator("text", "annotation_note")(valid_unicode)

    @model_validator(mode="after")
    def grounded_references(self):
        if len(self.text.encode("utf-8")) > 200000:
            raise ValueError("Source exceeds the literal learning byte contract")
        fields = {(item.kind, item.key) for item in self.requested_fields}
        if len(fields) != len(self.requested_fields):
            raise ValueError("Requested task fields must be unique")
        if any((item.kind, item.key) not in fields for item in self.expected):
            raise ValueError("Reference is outside requested task fields")
        spans = proposals(self.expected, self.text)
        if len(set(spans)) != len(spans):
            raise ValueError("Reference spans must be unique")
        return self


class Dataset(StrictModel):
    schema_version: Literal[1]
    dataset_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    scope: str = Field(min_length=1, max_length=2000)
    cases: list[BenchmarkCase] = Field(min_length=1, max_length=100)
    _unicode = field_validator("scope")(valid_unicode)

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("Schema version must be an integer")
        return value

    @model_validator(mode="after")
    def unique_cases(self):
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Benchmark case IDs must be unique")
        return self


class Prediction(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    response: str | dict | None = None
    error: Literal["provider_failure", "budget_rejected", "not_attempted"] | None = None

    @model_validator(mode="after")
    def one_outcome(self):
        if (self.response is None) == (self.error is None):
            raise ValueError("Supply exactly a response or a classified error")
        return self


class Predictions(StrictModel):
    schema_version: Literal[1]
    dataset_id: str
    producer: str = Field(min_length=1, max_length=160)
    run_kind: Literal["scripted", "manual", "model"]
    cases: list[Prediction] = Field(max_length=100)
    _unicode = field_validator("dataset_id", "producer")(valid_unicode)

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("Schema version must be an integer")
        return value

    @model_validator(mode="after")
    def unique_cases(self):
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Prediction case IDs must be unique")
        return self


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def proposals(items, text):
    response = {"candidates": [item.model_dump(exclude_none=True) for item in items]}
    return fingerprints(literal_candidates(encoded(response), text, SOURCE, "notes"))


def fingerprints(candidates):
    return [
        (item.entry.kind, item.entry.key, item.start, item.end) for item in candidates
    ]


def read_json(path):
    # Explicit file only; bounded read protects against an unexpectedly large prediction dump.
    with Path(path).open("rb") as stream:
        body = stream.read(MAX_JSON_BYTES + 1)
    if len(body) > MAX_JSON_BYTES:
        raise ValueError("Evaluation JSON exceeds 1 MiB")
    return json.loads(body.decode("utf-8"), object_pairs_hook=_unique_pairs)


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def score(dataset: Dataset, predictions: Predictions):
    if predictions.dataset_id != dataset.dataset_id:
        raise ValueError("Prediction dataset ID does not match")
    by_id = {item.id: item for item in predictions.cases}
    if set(by_id) - {case.id for case in dataset.cases}:
        raise ValueError("Prediction contains an unknown case ID")
    rows = []
    for case in dataset.cases:
        reference = Counter(proposals(case.expected, case.text))
        predicted = by_id.get(case.id)
        actual = Counter()
        submitted = aligned = 0
        valid = False
        status = (
            "missing"
            if predicted is None
            else "error"
            if predicted.error
            else "invalid"
        )
        if predicted is not None and predicted.response is not None:
            raw = predicted.response
            try:
                raw = (
                    json.loads(raw, object_pairs_hook=_unique_pairs)
                    if isinstance(raw, str)
                    else raw
                )
                items = raw.get("candidates") if isinstance(raw, dict) else None
                submitted = len(items) if isinstance(items, list) else 1
                if isinstance(items, list):
                    for item in items:
                        try:
                            literal_candidates(
                                encoded({"candidates": [item]}),
                                case.text,
                                SOURCE,
                                "notes",
                            )
                            aligned += 1
                        except (
                            MemoryInputError,
                            ValueError,
                            TypeError,
                            RecursionError,
                        ):
                            pass
                candidates = literal_candidates(
                    encoded(raw), case.text, SOURCE, "notes"
                )
                actual = Counter(fingerprints(candidates))
                valid = True
                status = "valid"
            except (MemoryInputError, ValueError, TypeError, RecursionError):
                # A malformed empty/missing object still represents one failed proposal attempt,
                # not successful abstention. Invalid batches never earn partial true positives.
                submitted = max(1, submitted)
        matched = sum((reference & actual).values()) if valid else 0
        rows.append(
            {
                "case_id": case.id,
                "status": status,
                "expected": sum(reference.values()),
                "submitted": submitted,
                "accepted": sum(actual.values()) if valid else 0,
                "literal_aligned": aligned,
                "matched": matched,
                "false_positives": submitted - matched,
                "false_negatives": sum(reference.values()) - matched,
                "exact_task_match": valid and actual == reference,
                "unsupported_abstention": not reference and valid and not actual,
            }
        )
    tp = sum(row["matched"] for row in rows)
    submitted = sum(row["submitted"] for row in rows)
    gold = sum(row["expected"] for row in rows)
    unsupported = sum(row["expected"] == 0 for row in rows)
    supported = len(rows) - unsupported
    metrics = {
        "cases": len(rows),
        "supplied_cases": len(predictions.cases),
        "reference_candidates": gold,
        "submitted_proposals": submitted,
        "true_positives": tp,
        "false_positives": sum(row["false_positives"] for row in rows),
        "false_negatives": sum(row["false_negatives"] for row in rows),
        "exact_candidate_precision": ratio(tp, submitted),
        "exact_candidate_recall": ratio(tp, gold),
        "exact_candidate_f1": ratio(2 * tp, submitted + gold),
        "individual_literal_alignment": ratio(
            sum(row["literal_aligned"] for row in rows), submitted
        ),
        "valid_batch_rate": ratio(
            sum(row["status"] == "valid" for row in rows), len(rows)
        ),
        "case_coverage": ratio(len(predictions.cases), len(rows)),
        "exact_task_match_rate": ratio(
            sum(row["exact_task_match"] for row in rows), len(rows)
        ),
        "supported_case_coverage": ratio(
            sum(row["expected"] > 0 and row["matched"] > 0 for row in rows), supported
        ),
        "unsupported_abstention": ratio(
            sum(row["unsupported_abstention"] for row in rows), unsupported
        ),
    }
    return {
        "dataset_id": dataset.dataset_id,
        "declared_producer": predictions.producer,
        "declared_run_kind": predictions.run_kind,
        "interpretation": "Exact hand-authored synthetic task/span agreement, not semantic equivalence, real-user prevalence or proof of actual model execution.",
        "metrics": metrics,
        "cases": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check-fixture", action="store_true")
    group.add_argument("--predictions", type=Path)
    parser.add_argument("--require-perfect", action="store_true")
    args = parser.parse_args(argv)
    try:
        dataset = Dataset.model_validate(read_json(args.dataset))
        if args.check_fixture:
            if args.require_perfect:
                raise ValueError("Perfect gating requires supplied predictions")
            print(
                f"SEMANTIC_BENCHMARK_FIXTURE PASS {len(dataset.cases)} cases; no model performance measured"
            )
            return 0
        predictions = Predictions.model_validate(read_json(args.predictions))
        report = score(dataset, predictions)
        print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
        return (
            1
            if args.require_perfect and report["metrics"]["exact_task_match_rate"] != 1
            else 0
        )
    except (
        OSError,
        UnicodeError,
        ValueError,
        MemoryInputError,
        RecursionError,
        ValidationError,
    ):
        print(
            "Semantic evaluation input is invalid or unavailable; no private input echoed.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
