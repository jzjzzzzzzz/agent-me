# Lesson 04 — Typed Handoffs and Orchestration

[Previous: Role design](../03-role-design/README.md) · [Course home](../README.md) · [简体中文](../translations/zh-CN/04-typed-orchestration/README.md) · [Next: Critic and observability](../05-critic-observability/README.md)

**Time:** 60–90 minutes · **Level:** Intermediate · **Produces:** a tested contract change

## Why this lesson matters

Coordination becomes fragile when every stage mutates one shared dictionary. A misspelled key may
fail far downstream, a role can overwrite another role's data, and no reviewer can see which fields
are stable. Typed handoffs turn assumptions into contracts that tools and tests can check.

Agent-Me uses two contract layers:

- frozen Python dataclasses for internal role artifacts;
- Pydantic and TypeScript types for the public HTTP boundary.

## Learning objectives

By the end, you can:

- trace ownership from `Plan` to `CollaborationResponse`;
- explain immutability and why `frozen=True` helps;
- distinguish internal artifacts from public schemas;
- identify invariants enforced by backend and browser parsers;
- modify a handoff and update every affected layer;
- avoid untyped “escape hatches” that erase the benefit.

## Contract map

```text
internal Python                              public HTTP / browser
──────────────────────────────────────      ─────────────────────────────
Plan                                         CollaborationRequest
EvidenceBundle          ┐                    CollaborationStage
Critique                ├─ orchestrator ─▶   CollaborationResponse
WrittenAnswer           │                    TypeScript response parser
StageTrace              ┘                    React view model
CollaborationResult
```

Internal artifacts may contain implementation details that never cross HTTP. Public schemas should
contain only stable, safe, caller-relevant information.

## Handoff invariants

| Artifact | Important invariants |
| --- | --- |
| `Plan` | retrieval query is normalized; tasks are ordered; query count is nonnegative |
| `EvidenceBundle` | matches preserve rank order; every source came from retrieval |
| `Critique` | grounded decision and bounded coverage describe current evidence |
| `WrittenAnswer` | blocked evidence yields zero citations |
| `StageTrace` | sequence is positive; agent/outcome are closed sets; metrics are safe scalars |
| `CollaborationResult` | server-generated run ID; workflow name; ordered stages |

Some are guaranteed by types, some by constructors, and some only by tests. A serious design review
must distinguish those enforcement levels.

## Read the implementation

1. Internal artifacts and roles: [`backend/app/collaboration.py`](../../backend/app/collaboration.py)
2. Public models: [`backend/app/schemas.py`](../../backend/app/schemas.py)
3. HTTP serialization: [`backend/app/main.py`](../../backend/app/main.py)
4. Browser types and runtime parser: [`frontend/src/api.ts`](../../frontend/src/api.ts)
5. Browser parser tests: [`frontend/src/api.test.ts`](../../frontend/src/api.test.ts)
6. UI rendering: [`frontend/src/App.tsx`](../../frontend/src/App.tsx)

Notice that TypeScript compile-time types cannot validate an arbitrary network response. The
runtime parser checks the actual JSON before React uses it.

## Hands-on lab

### Step 1 — inspect immutable artifacts

Run:

```bash
.venv/bin/python - <<'PY'
from dataclasses import FrozenInstanceError
from app.collaboration import Plan

plan = Plan(retrieval_query="agent planning", tasks=("retrieve",), query_term_count=2)
try:
    plan.query_term_count = 99
except FrozenInstanceError as error:
    print(type(error).__name__)
PY
```

The tuple also prevents list-style mutation of tasks. Immutability does not make nested mutable
objects safe automatically; each field type still matters.

### Step 2 — follow one field end to end

Trace `query_coverage`:

1. calculated in `CriticAgent.run`;
2. stored in `Critique`;
3. copied into critic `StageTrace.metrics`;
4. serialized by Pydantic;
5. checked as a finite scalar in TypeScript;
6. displayed by the React trace viewer.

Write the same path for `run_id`, including where its format is enforced.

### Step 3 — run contract tests

```bash
.venv/bin/pytest -q backend/tests/test_collaboration.py backend/tests/test_api.py
cd frontend
npm test -- --run src/api.test.ts src/App.test.tsx
cd ..
```

### Step 4 — make a controlled internal change

Add `document_count: int` to `EvidenceBundle` rather than recomputing it in the orchestrator.
Update the researcher, trace creation, and tests. Decide whether it belongs in the public response
outside trace metrics; do not expose it merely because it exists internally.

Verification:

```bash
make lint
make test
make evaluate
```

If you prefer not to retain the exercise, perform it on a learner branch and reset after recording
the diff.

## Contract evolution strategy

Before changing a public field:

1. identify producers and consumers;
2. decide whether the change is additive or breaking;
3. update server model and serialization;
4. update runtime browser parsing—not only TypeScript declarations;
5. add valid and invalid response fixtures;
6. update UI states and documentation;
7. run integration and container smoke tests;
8. version the API if existing clients cannot migrate safely.

For internal fields, the surface is smaller, but evaluation behavior may still change.

## Why not `dict[str, Any]`?

An unrestricted dictionary allows fast experimentation but moves correctness to runtime and human
memory. It permits:

- missing fields;
- ambiguous types;
- silent overwrite;
- accidental serialization of private data;
- stage-specific data leaking to unrelated roles.

Use a typed metadata extension only when keys and values are genuinely open-ended, and constrain
what crosses public or logging boundaries. Agent-Me restricts trace metrics to booleans and finite
numbers for this reason.

## Exercises

### Required — classify enforcement

For five invariants, record whether each is enforced by:

- static type checker;
- constructor/model validation;
- runtime parser;
- unit test;
- behavioral evaluation;
- or documentation only.

Choose one documentation-only invariant and add executable enforcement.

### Intermediate — add a verifier role

Insert `VerifierAgent` between critic and writer. Its artifact may contain mechanically checkable
facts such as:

- all citation paths exist in the evidence bundle;
- blocked critique implies zero citations;
- answer length is below a configured maximum.

Update agent-name literals, stage counts and order, Python schemas, TypeScript parser, tests,
evaluation, diagram, and docs. Do not use an arbitrary dictionary handoff.

### Advanced — version a public workflow

Compare the implemented `baseline` and `verified` policies. Explain how the workflow discriminator
lets a client select the expected four- or five-stage contract before validating agent order.
Add a parser test that gives the verified workflow identifier a four-stage trace and confirms it is
rejected.
Compare a new endpoint, workflow discriminator, and media/API version. Explain your compatibility
choice.

## Check your understanding

1. Why are Pydantic models and TypeScript interfaces not redundant?
2. Which nested mutable values could still undermine a frozen dataclass?
3. When should an internal artifact field remain private?
4. Why must invalid network-response tests exist?
5. What makes a schema change breaking even if the backend still starts?

## Completion checklist

- [ ] I can draw the internal and public contract layers.
- [ ] I traced two fields from creation to browser rendering.
- [ ] I ran backend and frontend contract tests.
- [ ] I changed one handoff without using `Any`.
- [ ] I classified invariants by enforcement mechanism.
- [ ] I can describe a safe public-contract migration.

## Further reading

- [Pydantic strict and constrained types](https://docs.pydantic.dev/latest/concepts/strict_mode/)
- [TypeScript handbook](https://www.typescriptlang.org/docs/handbook/intro.html)
- [Semantic Versioning](https://semver.org/)

---

**Previous: [Lesson 03](../03-role-design/README.md)** · **Next: [Lesson 05 — Critic gates and safe observability](../05-critic-observability/README.md)**
