# Lesson 07 — Production Design and Portfolio Capstone

[Previous: Evaluation](../06-evaluation/README.md) · [Course home](../README.md) · [简体中文](../translations/zh-CN/07-production-capstone/README.md) · [Rubric](../RUBRIC.md)

**Time:** 90 minutes to 3 days · **Level:** Intermediate–Advanced · **Produces:** ADR, extension, measurements, demo

## Why this lesson matters

A correct in-process workflow is not automatically reliable after adding multiple workers, external
models, user accounts, persistent traces, or untrusted tenants. Production design is the discipline
of identifying which guarantees disappear at each new boundary and adding explicit mechanisms and
tests.

The capstone asks you to improve the system without claiming properties you have not implemented.

See the complete [evidence-based verified-policy sample capstone](../examples/verified-policy-capstone/README.md) for a reproducible submission with rejected alternatives, measured output, privacy review, limitations, and an honest portfolio statement.

## Learning objectives

By the end, you can:

- separate current guarantees from desired guarantees;
- reason about at-least-once execution, idempotency, retries, and cancellation;
- design durable workflow state and safe trace retention;
- select and implement one bounded extension;
- measure behavior before and after;
- write an architecture decision record (ADR);
- present a technically defensible portfolio story.

## Current guarantees

The baseline implements and tests:

- strict request models and body-size limits;
- deterministic local retrieval and role order;
- server-controlled run IDs;
- frozen internal handoff artifacts;
- approved and blocked critic paths;
- optional post-write verification with fail-closed citation invariants;
- strict browser response parsing;
- safe plain-text rendering;
- no persistence of questions or collaboration traces;
- lint, unit/contract/integration tests, evaluation, and container smoke checks.

## Guarantees not provided by the baseline

- durable state after process restart;
- multi-worker coordination;
- exactly-once stage execution;
- model-provider redundancy or budget enforcement;
- authentication, authorization, or tenant isolation;
- encrypted trace storage and retention jobs;
- semantic retrieval quality at production corpus scale;
- formal answer faithfulness;
- service-level objectives or incident response.

Do not hide this list. It is the starting point for credible system design.

## From local calls to durable workflow

A distributed version might persist:

```text
Run(id, tenant, status, version, created_at, deadline)
Stage(run_id, name, attempt, status, input_ref, output_ref, lease_until)
Event(run_id, sequence, type, safe_metadata, created_at)
```

Workers claim a stage atomically, write idempotent output, and append events. Important questions:

### Delivery semantics

Most queues provide at-least-once delivery. A worker can finish work and crash before acknowledging,
so the same message arrives again. Your stage must use a stable idempotency key and conditional
state transition.

### Timeouts and retries

Retry only failures likely to be transient. Apply bounded attempts, exponential backoff with jitter,
and a total run deadline. Invalid input and policy blocks are terminal outcomes, not retry storms.

### Cancellation

Cancellation must be persisted and checked before costly work and before output commit. A client
disconnect is not a reliable in-memory cancellation signal across workers.

### Backpressure

Limit queued runs, per-tenant concurrency, provider concurrency, and output size. Otherwise a burst
can exhaust database connections, memory, provider quota, or cost budget.

### Trace privacy

Store structured codes and safe metrics by default. Define retention, deletion, tenant access, and
redaction before persisting prompts or excerpts.

## Read the implementation

Revisit the boundaries you may extend:

1. [`collaboration.py`](../../backend/app/collaboration.py) for role state and sequencing;
2. [`main.py`](../../backend/app/main.py) for process-local HTTP execution;
3. [`request_limits.py`](../../backend/app/request_limits.py) for admission limits;
4. [`docker-compose.yml`](../../docker-compose.yml) for current process topology;
5. [`ci.yml`](../../.github/workflows/ci.yml) for packaged verification.

For each file, write which guarantee would be lost or need redesign after adding workers or persistence.

## Capstone options

Choose **one** bounded implementation. Depth and evidence matter more than feature count.

### Option A — Extend the verifier policy

The reference implementation now includes a fifth typed verifier role. Extend it with one measured
policy such as citation syntax parsing, per-source allowlists, or claim-to-source mapping. Add
positive, negative, and false-positive cases; do not rename mechanical checks as truth verification.

### Option B — Retrieval quality upgrade

Add a second ranking strategy behind configuration. Create relevance labels, compare precision and
recall, measure latency, document fallback behavior, and keep deterministic tests.

### Option C — Durable local runs

Persist run/stage status in SQLite or PostgreSQL with migration and idempotent updates. Add restart
and duplicate-execution tests. Do not persist raw prompts by default.

### Option D — Authentication and tenant isolation

Add an established authentication approach and scope knowledge/runs by tenant. Test IDOR prevention,
role authorization, data deletion, and secret redaction.

### Option E — Provider-backed role experiment

Allow one role to call an OpenAI-compatible provider behind explicit configuration. Add timeouts,
error taxonomy, response limits, privacy documentation, mock contract tests, and a disabled-by-default
mode. Report cost/latency only from runs you actually measured.

## Hands-on lab: Required architecture decision record

Create `docs/adr/0001-<decision>.md` in your fork:

```markdown
# ADR 0001: <decision>

## Status
Proposed | Accepted | Superseded

## Context
What measured problem or requirement exists?

## Decision
What will be built, including boundaries and invariants?

## Alternatives considered
At least two, including doing nothing.

## Consequences
Benefits, costs, failure modes, privacy, operations, migration.

## Verification
Tests, evaluation cases, metrics, rollback signal.
```

An ADR is not marketing copy. Include rejected alternatives and negative consequences.

## Required implementation workflow

1. Create a focused issue and branch.
2. Record baseline tests and evaluation.
3. Write or update the ADR before large code changes.
4. Add a failing test or evaluation case for the desired behavior.
5. Implement the smallest complete vertical slice.
6. Update Python and TypeScript contracts together when public data changes.
7. Add failure-path and boundary tests.
8. Update English docs and affected translations.
9. Run the complete quality gate.
10. Capture measured results and known limitations.

Commands:

```bash
make lint
make test
make docs
make evaluate
make build
```

## Production review checklist

### Correctness

- Are state transitions atomic?
- Can duplicate delivery produce duplicate side effects?
- Is output associated with the correct run and tenant?
- Are time, order, and IDs server-controlled?

### Reliability

- Are timeouts bounded at every network boundary?
- Which errors retry, and how many times?
- What happens after restart?
- Is there backpressure and graceful degradation?

### Security and privacy

- Who can read knowledge, traces, and outputs?
- Are request bodies and files size-limited before expensive processing?
- Are secrets excluded from Git, responses, and logs?
- Are retention and deletion implemented and tested?

### Observability

- Can an operator locate the failing stage from a run ID?
- Are metrics cardinality and content bounded?
- Do alerts correspond to user impact?
- Can a rollback be verified?

### Evaluation

- Are labels versioned with corpus and code?
- Are unsupported and adversarial cases included?
- Are metrics reported with case counts and confidence limitations?
- Does CI protect known regressions?

## Exporting a sanitized run artifact

After a completed collaboration run, the frontend can download a UTF-8 JSON record containing only
`run_id`, `workflow`, `mode`, `answer`, `grounded`, `sources`, and `trace`. The artifact deliberately
excludes the submitted question, profile metadata, provider configuration, and hidden browser state.
Use it as supporting evidence alongside the commit, commands, tests, and limitations—not as a
replacement for those materials or as proof of production quality.

## Exercises: Portfolio package

Produce:

1. a two-minute architecture walkthrough;
2. a live approved and blocked request;
3. a diagram of role contracts;
4. test/evaluation output from a clean commit;
5. your capstone ADR and pull request;
6. one slide or README section with measured before/after results;
7. a limitations section.

### Defensible resume bullet

Base course:

> Built and tested a backward-compatible in-process multi-agent orchestration API with baseline
> (planner → researcher → critic → writer) and verified (+ verifier) policies, typed immutable
> handoffs, grounded Markdown retrieval, fail-closed citation invariants, runtime-validated traces,
> deterministic evaluations, and a FastAPI/React/TypeScript interface.

What that sentence is evidence for:

| Claim | Repository evidence |
| --- | --- |
| backward-compatible policies | strict `workflow` request enum and separate workflow identifiers |
| typed handoffs | frozen Python dataclasses, Pydantic response models, TypeScript types |
| fail-closed verification | verifier replaces a rejected candidate with a fixed safe response |
| contract validation | Python route tests plus TypeScript runtime parser tests |
| end-to-end integration | container CI calls the API through the same-origin Nginx gateway |

It is not evidence for distributed workers, multiple LLMs, semantic truth guarantees, or production
SLOs. State those as future design work unless you implement and measure them.

After your capstone, add only measured facts:

> Added **N** labeled evaluation cases across **categories**, improved grounded-decision precision
> from **A/B** to **C/D** on the versioned fixture set, and enforced regressions in CI.

Do not write “distributed,” “autonomous,” “production-ready,” “hallucination-free,” or “multiple
LLMs” unless your implementation and tests demonstrate those exact properties.

## STAR interview outline

- **Situation:** The original Q&A path returned results but made evidence and approval decisions hard
  to inspect.
- **Task:** Create explicit collaboration boundaries and measurable failure behavior.
- **Action:** Describe the artifacts, critic policy, strict API/browser contracts, evaluation cases,
  and your capstone tradeoff.
- **Result:** Give exact passing test counts or evaluation fractions, latency/cost measurements if
  collected, and known limitations.

## Check your understanding: Interview questions

1. Why can exactly-once processing rarely be assumed from a queue?
2. Where would you persist idempotency keys and stage leases?
3. Which current invariants survive if roles become workers?
4. How would a tenant prove their traces are isolated and deletable?
5. What does your evaluation measure, and what does it not generalize to?
6. When would you rollback your capstone change?
7. Which alternative did your ADR reject and why?
8. What would you simplify if the workload stayed small?

## Completion checklist

- [ ] I selected one bounded capstone with explicit non-goals.
- [ ] I recorded baseline results.
- [ ] I wrote an ADR with alternatives and consequences.
- [ ] I added failing verification before or alongside implementation.
- [ ] I completed a vertical slice including failure behavior.
- [ ] Full lint, tests, docs, evaluation, and build pass.
- [ ] I reported measurements with case counts and limitations.
- [ ] My demo shows approved and blocked behavior.
- [ ] My portfolio wording matches the implementation exactly.
- [ ] I reviewed my work against [`course/RUBRIC.md`](../RUBRIC.md).

## Further reading

- [Google SRE Book](https://sre.google/sre-book/table-of-contents/)
- [AWS Builders' Library: retries and backoff](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)
- [Architecture Decision Records](https://adr.github.io/)

---

**Previous: [Lesson 06](../06-evaluation/README.md)** · **Return to [course home](../README.md)** · **Review the [rubric](../RUBRIC.md)**
