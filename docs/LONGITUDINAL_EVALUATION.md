# Longitudinal personal-Agent evaluation

Run `make evaluate-longitudinal` or
`.venv/bin/python scripts/evaluate_longitudinal.py --json`. The evaluator creates and
destroys a fictional workspace; it does not inspect owner files, load environment/provider
configuration, send network requests or imitate a real person.

Twenty independently labeled stages cover pending/accepted facts, stale review rejection,
correction-before/after-acceptance, obsolete value exclusion, owner identity, a contradictory
alias, correction of that contradiction, valid time vs learned time, expiry, sensitive opt-in,
preference changes/deletion, injection-as-data, and forgetting. Expected statuses/values are
fixture labels, not copied from the Agent's output. Real `PersonalAgent.ask` results feed the
metrics; live retrieval/verification and provenance IDs are exercised at every stage.

## Defined measures

| Metric | Definition |
| --- | --- |
| Status accuracy | Exact expected epistemic status / all observations |
| Supported-question coverage | Questions with all labeled expected values in verified claims / supported questions |
| Unsupported abstention | Labeled unknown questions with no verified claim / unknown questions |
| Provenance coverage | Claims matching returned evidence ID, kind, subject, field, value, belief and confidence / emitted claims |
| Privacy leak rate | Restricted/deleted-value cases whose returned data contains a forbidden fixture marker / restricted cases |
| Preference fidelity | Expected presentation style / explicitly style-labeled cases; preference-shaped facts cannot substitute for identity |
| Declared-confidence Brier | Mean `(declared record confidence - independent fixture correctness label)^2` for claims with numeric confidence |
| Declared-confidence coverage | Numerically scored claims / all claims |
| Correction effort | Accepted/rejected owner mutations and mean operations per completed correction |

Confidence is never inferred from the word `known`, model prose or retrieval score. Null
confidence remains unscored. Zero denominators/unavailable calibration produce JSON null,
not a fake perfect zero/one. The calibration fixture deliberately includes a wrong competing
name with declared confidence; disputed claims remain uncertain. This measures declared
record calibration against fictional labels, not LLM probabilities or population performance.

The fixture performs three completed corrections: edit+confirm a fact (2 accepted ops),
delete a wrong competing alias (1), and edit+confirm style (2). One stale fact-edit attempt
is rejected. Initial ingestion/review and final forgetting are not counted as corrections.
Thus successful operations =5, attempts =6, mean attempted operations =2. This is a
reproducible operation-cost measure, not elapsed human effort or usability-study evidence.

## Current fixture result

The implemented fixture yields 20/20 expected statuses, 100% supported coverage/unknown
abstention/provenance/style fidelity, zero restricted-marker leaks, 8 numeric calibration
samples, declared-confidence coverage 0.8 and Brier approximately 0.08875. These values are
synthetic acceptance evidence, not claims about real-world truth, semantic entailment,
embedding quality or personality imitation. Exact source verification does not prove truth.

Tests rerun the entire fixture for equality, check missing denominators, and mutate retrieval
to remove all evidence: supported coverage falls to zero, calibration becomes unavailable,
and the evaluator fails. Existing memory/learning/identity/retrieval/agency/owner-control
suites remain separate so this aggregate report cannot hide a category regression.
All evaluations run on the CI Python 3.11, Python 3.12 and Windows workflows.
