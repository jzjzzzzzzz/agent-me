# Offline semantic proposal evaluation

The [versioned synthetic fixture](../course/fixtures/semantic_cases.json) and
[`evaluate_semantic_learning.py`](../scripts/evaluate_semantic_learning.py) make extraction quality
inspectable **without invoking a provider, reading credentials or touching an owner workspace**.
They complement [semantic learning contract tests](SEMANTIC_LEARNING.md), not replace owner review.

## What is annotated

`semantic-literal-owner-v1` contains 12 hand-authored English/Chinese/mixed cases, 10 positive reference
candidates in seven cases and five requested-field abstention cases. Each case independently declares:

- source text and language;
- requested kind/key pairs defining the specific task;
- exact supported quotation/codepoint intervals; and
- a written annotation rationale.

The negative tasks distinguish negation, third-person preference, a hypothetical decision, source
instructions and unrelated public text from a positive owner assertion in the requested field. Repeated
names and a leading emoji test source attribution/offsets. Relative event time remains quotation text,
not an invented UTC occurrence. References themselves pass the actual literal-span validator; duplicate
IDs/spans, unsupported source quotes, wrong requested fields and ambiguous offsets invalidate the fixture.

These are **small synthetic, authored exact-task references**. They are not an independently reviewed
real-user dataset, prevalence estimate or universal semantic-equivalence ground truth. A valid alternative
field, quotation boundary or interpretation may not match this exact task. Real experiments should
predefine acceptable alternatives, use separate annotators/adjudication and declare exclusion rules
before inspecting predictions. The fixture does not encode instructions inside text as trusted authority.

## No performance score from checking labels

```bash
make evaluate-semantic
# SEMANTIC_BENCHMARK_FIXTURE PASS 12 cases; no model performance measured
```

This only validates the fixture. It does not call a model, copy labels into a hidden prediction run or
publish an accuracy/F1 number. Normal CI runs this validation and independent scorer mutation tests.

## Scoring an explicitly supplied prediction file

Predictions must declare the same dataset ID, producer identifier and `run_kind` (`model`, `manual`
or `scripted`). Those declarations are metadata, **not proof of actual model execution**. Supply raw
candidate content, not corrected owner-confirmed memory records disguised as model output. The learning
adapter intentionally does not persist raw provider responses; record predictions through a separately
authorized evaluation path or an authorized existing run recorder. This scorer never bypasses disclosure
consent or starts a paid/provider request.

```json
{
  "schema_version": 1,
  "dataset_id": "semantic-literal-owner-v1",
  "producer": "declared-method-version",
  "run_kind": "manual",
  "cases": [
    {
      "id": "en-name-style",
      "response": {
        "candidates": [
          {"kind": "fact", "key": "identity.name", "quote": "Alex Example", "start": 5}
        ]
      }
    },
    {"id": "name-negation", "response": {"candidates": []}},
    {"id": "hypothetical-decision", "error": "not_attempted"}
  ]
}
```

This example deliberately omits cases/candidates and is **not** a perfect prediction fixture. A response
can also be a raw JSON content string, allowing malformed model output to be scored as an invalid batch.
Classified errors are `provider_failure`, `budget_rejected` or `not_attempted`; response and error are
mutually exclusive. Unknown/duplicate case IDs, a different dataset or unsupported versions are input
errors rather than silently excluded cases. JSON reads are capped at 1 MiB and duplicate outer JSON
fields are rejected. Only files explicitly passed on the command line are read.

```bash
.venv/bin/python scripts/evaluate_semantic_learning.py --predictions /path/to/predictions.json
# JSON report to stdout; no source text, quotations or raw model response in the report
```

The default exit status 0 means a valid evaluation/report, **not a good model**. Use `--require-perfect`
only when you deliberately want an exact-task regression gate: it exits 1 when the entire task set does
not match; invalid/unavailable input exits 2 with a generic message, without echoing the input. To use
another explicitly annotated fixture, pass `--dataset` and declare its matching dataset ID.

## Denominators and failure behavior

A true positive is a multiset match of `(kind, key, start, end)` against the current case reference.
Literal equality fixes quote/value text; kind/key and exact location remain separate. Duplicate predictions
can match a reference only once; extra duplicates and out-of-task fields count as false positives.
A rejected batch earns **zero** partial true positives, even if some quotes were individually valid.

| Metric | Definition |
| --- | --- |
| `exact_candidate_precision` | TP / submitted proposal count; null if none were submitted |
| `exact_candidate_recall` | TP / reference count; null if no references exist |
| `exact_candidate_f1` | 2TP / (submitted + reference count); null only when both are zero |
| `individual_literal_alignment` | Individually contract-valid exact-span proposals / submitted count; does not establish field meaning |
| `valid_batch_rate` | Fully contract-valid response cases / all fixture cases |
| `case_coverage` | Supplied case entries, including declared errors, / all fixture cases |
| `exact_task_match_rate` | Valid, exactly matching multisets / all fixture cases |
| `supported_case_coverage` | Positive-reference cases with at least one TP / positive-reference cases |
| `unsupported_abstention` | Empty valid responses / zero-reference cases |

Missing cases/errors are not successful abstention and positive references still contribute false
negatives. A malformed empty/missing object is one failed submitted attempt, not a valid empty result.
All-empty valid responses can score abstention well but have zero positive recall/F1; the scorer never
turns absent predictions into a perfect overall score. Individual alignment may be 1.0 while a negated
or third-person value has zero exact-task agreement. This specifically tests the gap between quote
provenance and meaning rather than hiding it behind a grounding label.

The report identifies declared provenance and includes per-case counts/status, but never source text,
quotes or raw provider bodies. Do not publish private prediction dumps just because an aggregate report
is content-limited. Evaluation does not change, approve or ingest any memory.

## Verification

Tests cover deterministic perfect **explicit scripted** inputs, misleading but exact negated quotes,
wrong labels, duplicated proposals, whole-batch rejection, missing/errors, all-empty output, Unicode/
repeated offsets, unsupported references, ID/version validation, bounded JSON, duplicate fields,
explicit perfect gating and redacted input errors. Their synthetic scores establish scorer correctness,
not performance of an actual LLM. Model quality remains unproven until separately authorized predictions
are produced and scored against an appropriate independently reviewed task set.
