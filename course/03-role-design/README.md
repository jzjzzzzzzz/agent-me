# Lesson 03 — Design Collaborating Roles

[Previous: Retrieval](../02-retrieval/README.md) · [Course home](../README.md) · [简体中文](../translations/zh-CN/03-role-design/README.md) · [Next: Typed orchestration](../04-typed-orchestration/README.md)

**Time:** 45–60 minutes · **Level:** Intermediate · **Produces:** a role-boundary decision record

## Why this lesson matters

“Multi-agent” is often used for any prompt containing several job titles. That does not create an
engineering boundary. Useful decomposition gives each role a clear responsibility, input, output,
and failure policy. It should improve observability, testing, isolation, or extensibility enough to
justify extra latency and complexity.

This lesson compares the repository's compact single-path endpoint with its four-role teaching
workflow and asks when the extra structure is worth keeping.

## Learning objectives

By the end, you can:

- define a role by contract and responsibility rather than persona text;
- explain planner, researcher, critic, and writer ownership;
- compare single-path and collaboration responses empirically;
- identify coordination overhead and coupling;
- state the exact scope of Agent-Me's “multi-agent” implementation;
- write a decision record for adding or rejecting a role.

## A useful role test

Before creating a role, answer five questions:

1. **Unique responsibility:** what decision belongs only to this role?
2. **Input contract:** what minimum artifact does it receive?
3. **Output contract:** what downstream code may rely on?
4. **Failure policy:** can it block, retry, degrade, or only report?
5. **Independent evidence:** how will you test that it improves the system?

If the answers are “same context,” “free-form text,” and “we call it another agent,” prefer one
function until a real boundary appears.

## Roles in the course implementation

| Role | Receives | Produces | Owns | Does not own |
| --- | --- | --- | --- | --- |
| Planner | normalized question | `Plan` | evidence-first task outline | retrieval results |
| Researcher | ranked `Match` objects | `EvidenceBundle` | evidence packaging | final approval |
| Critic | question + evidence | `Critique` | grounded/block decision | answer wording |
| Writer | evidence + critique | `WrittenAnswer` | response composition | source discovery |

The orchestrator owns sequence and public trace construction. Roles do not call each other
directly. This reduces hidden coupling and makes substitution possible.

## Exact scope of “multi-agent”

Agent-Me implements **role-based multi-agent orchestration in one Python process**:

- four objects have separate responsibilities;
- typed artifacts cross boundaries;
- an orchestrator controls execution order;
- each stage produces safe operational trace data;
- tests exercise approved and blocked paths.

It does not currently implement:

- multiple language models;
- autonomous planning loops;
- concurrent or distributed workers;
- durable workflow state;
- inter-agent network protocols;
- model chain-of-thought exposure.

Precision is a strength. It lets reviewers distinguish implemented evidence from future design.

## Read the implementation

Read [`backend/app/collaboration.py`](../../backend/app/collaboration.py) in this order:

1. type aliases for agent names, outcomes, and metrics;
2. frozen artifact dataclasses;
3. each role's `run` method;
4. `CollaborationOrchestrator.__init__` dependency injection;
5. `CollaborationOrchestrator.run` sequencing and trace creation.

Then compare the `/api/v1/chat` and `/api/v1/collaborate` routes in
[`backend/app/main.py`](../../backend/app/main.py).

## Hands-on lab

### Step 1 — run one question through both paths

Start the API:

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --reload
```

Single path:

```bash
curl --silent http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"How does the example agent plan a project?"}' \
  | python3 -m json.tool
```

Collaboration path:

```bash
curl --silent http://localhost:8000/api/v1/collaborate \
  -H 'Content-Type: application/json' \
  -d '{"question":"How does the example agent plan a project?"}' \
  | python3 -m json.tool
```

### Step 2 — compare contracts

Record:

| Property | Single path | Collaboration path |
| --- | --- | --- |
| sources visible | yes | yes |
| answer mode | extractive/provider | local collaboration |
| run identity | no | yes |
| explicit grounded decision | implicit | yes |
| role trace | no | four stages |
| extension surface | smaller | typed role boundary |

### Step 3 — test dependency substitution

`CollaborationOrchestrator` accepts role instances in its constructor. Create a small test double
for one role and verify the orchestrator uses it. The double must return the same typed artifact;
do not bypass the contract with an arbitrary dictionary.

This demonstrates an important property: **separate roles are useful when behavior can be changed
or tested at a boundary**.

### Step 4 — measure overhead honestly

Use a small loop or HTTP timing tool to compare local latency for the two endpoints. Record hardware,
commit, number of runs, warm-up policy, median, and an upper percentile. Do not advertise a
benchmark from one request.

The local roles perform little work, so the difference may be small. In a provider-backed design,
each sequential model call could dominate latency and cost.

## Design tradeoffs

### Benefits

- role-specific tests and ownership;
- explicit approval gate before writing;
- inspectable execution stages;
- easier insertion of a verifier or policy role;
- public vocabulary for discussing failure location.

### Costs

- more artifact and schema types;
- sequence coupling across backend and frontend;
- additional tests and migration work;
- potential latency/cost if roles call external models;
- risk of ceremonial roles that add no independent value.

The right comparison is not “multi-agent is advanced.” It is “does this boundary create measured
value for this workload?”

## Exercises

### Required — role decision record

Choose one proposed role: verifier, router, privacy reviewer, or formatter. Write one page containing:

- problem and current failure mode;
- input and output artifact fields;
- invariant owned by the role;
- placement in the sequence;
- blocked/retry behavior;
- tests and evaluation cases;
- expected cost and latency;
- rejection criteria if it adds no value.

### Intermediate — remove a ceremonial role

Imagine the planner always returns the same three tasks and no downstream role reads them. Argue
for retaining, changing, or removing it. Base the decision on observable behavior, not the role name.

### Advanced — parallel research design

Design two researcher roles that can execute independently, then a merge contract. Address stable
ordering, duplicate evidence, partial failure, timeout, and provenance. No implementation is
required yet.

## Check your understanding

1. What property makes two role objects more than two personas?
2. Why does the orchestrator—not the roles—own ordering?
3. When is a single function preferable?
4. How would four external model calls change cost and reliability?
5. Which evidence would convince you that a new critic improved behavior?

## Completion checklist

- [ ] I can define every role's input, output, and responsibility.
- [ ] I compared both API paths using the same question.
- [ ] I can state what the project does not claim.
- [ ] I tested or designed substitution at one typed boundary.
- [ ] I wrote a role decision record with rejection criteria.
- [ ] I can explain benefits and costs without saying “more agents is better.”

## Further reading

- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html)
- [Martin Fowler: bounded context](https://martinfowler.com/bliki/BoundedContext.html)
- [Google SRE: managing critical state](https://sre.google/sre-book/management-of-critical-state/)

---

**Previous: [Lesson 02](../02-retrieval/README.md)** · **Next: [Lesson 04 — Typed handoffs and orchestration](../04-typed-orchestration/README.md)**
