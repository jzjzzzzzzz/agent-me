# Sample capstone — Add a fail-closed verifier policy

[Course home](../../README.md) · [Lesson 07](../../07-production-capstone/README.md) · [简体中文](README.zh-CN.md)

This is a reproducible example of a capstone submission, not a claim about production traffic or
semantic truth. It uses only the deterministic local runtime and the public fixtures in this
repository; no API key or paid provider is required.

## Problem and measurable acceptance criteria

The baseline collaboration workflow stopped after the writer. A malformed citation path or an
inconsistent `grounded` flag could therefore cross the final response boundary unless every writer
path preserved those invariants.

The extension is accepted when:

1. baseline requests keep the four-stage workflow identifier and behavior;
2. verified requests add exactly one final `verifier` stage;
3. the verifier accepts response metadata and citation paths that match retrieved sources;
4. a failed invariant produces a fixed blocked answer rather than the candidate answer;
5. all four committed evaluation labels pass under both policies.

## Architecture decision

**Decision:** add a fifth, local deterministic verifier after the writer, selected by an explicit
`verified` request policy. The verifier checks mechanical response invariants and returns a typed
artifact. The HTTP response keeps the baseline contract while using a distinct five-stage workflow
identifier.

**Rejected alternative:** put the checks inside the writer. That uses less code, but the same role
would create and approve its own output, and a writer refactor could accidentally bypass the gate.

**Rejected alternative:** call a second model as a semantic judge. That would add cost, latency,
provider disclosure, nondeterminism, and a new failure boundary without proving truth. It is outside
this local example.

## Public fixtures used

- Knowledge fixture: [`knowledge/example-profile.md`](../../../knowledge/example-profile.md)
- Evaluation labels: [`course/fixtures/collaboration_cases.json`](../../fixtures/collaboration_cases.json)
- Orchestrator and typed artifacts: [`backend/app/collaboration.py`](../../../backend/app/collaboration.py)
- API contract tests: [`backend/tests/test_api.py`](../../../backend/tests/test_api.py)
- Browser parser tests: [`frontend/src/api.test.ts`](../../../frontend/src/api.test.ts)

The evaluation set contains two supported and two unsupported questions. Four cases are sufficient
to detect the demonstrated regressions, not to estimate broad real-world quality.

## Reproduce the evidence

From a fresh clone:

```bash
make setup
make lint
make test
make docs
.venv/bin/python scripts/evaluate_collaboration.py --json
.venv/bin/python scripts/evaluate_collaboration.py --workflow verified --json
```

Observed on the committed public fixtures:

```text
baseline: 4/4 passed; trace length 4
verified: 4/4 passed; trace length 5
supported cases: 2 grounded, each with 1 source
unsupported cases: 2 blocked, each with 0 sources
```

These counts are produced by the commands above. They are not user, traffic, latency, or accuracy
claims.

## Before and after evidence

| Behavior | Before: baseline | After: verified policy |
| --- | --- | --- |
| Role order | planner → researcher → critic → writer | planner → researcher → critic → writer → verifier |
| Final mechanical invariant gate | writer-owned only | separate typed verifier artifact |
| Invalid citation/metadata outcome | depended on writer path | fixed fail-closed blocked response |
| Existing evaluation labels | 4/4 | 4/4 |
| External provider | none | none |

The change improves separation of duties and makes one class of contract failure observable. It
does not prove that every supported sentence is semantically entailed by its source.

## Security and privacy review

- Questions and traces remain process-local and are not persisted by the reference implementation.
- Run IDs are server-controlled and contain no question text.
- Trace summaries and metrics are bounded operational artifacts, not hidden reasoning.
- The verifier performs no network call and receives no secret.
- Citation paths are checked against the retrieved public source set.
- The browser's **Download sanitized run JSON** action exports only the validated collaboration
  response; it excludes the submitted question, profile, provider settings, and hidden state.

## Known limitations and next experiment

Current limitations:

- lexical retrieval can miss semantic paraphrases;
- citation membership is mechanical, not semantic entailment;
- execution is synchronous and process-local;
- four evaluation cases do not characterize production quality;
- there is no durable cancellation, tenant isolation, or SLO.

Next experiment: add claim-to-source sentence mapping behind a typed verifier artifact, then create
false-positive and false-negative labels before changing the policy. Compare the new labels against
the same baseline rather than replacing the evidence set after observing results.

## Honest portfolio statement

> Added and tested an opt-in fifth verifier role to a local FastAPI multi-agent workflow, preserving
> the four-stage baseline while enforcing fail-closed citation and response-metadata invariants; both
> policies passed the repository's four deterministic public evaluation cases.

This statement does not claim real users, distributed workers, production scale, semantic truth, or
provider-backed multi-model execution.
