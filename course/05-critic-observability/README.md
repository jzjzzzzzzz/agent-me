# Lesson 05 — Critic Gates and Safe Observability

[Previous: Typed orchestration](../04-typed-orchestration/README.md) · [Course home](../README.md) · [简体中文](../translations/zh-CN/05-critic-observability/README.md) · [Next: Evaluation](../06-evaluation/README.md)

**Time:** 45–60 minutes · **Level:** Intermediate · **Produces:** approved/blocked trace evidence

## Why this lesson matters

An agent system needs to answer two different questions:

1. should the workflow continue?
2. what can operators and users safely observe?

A critic role can gate unsupported synthesis, while an operational trace can reveal sequence,
status, counts, latency, and policy outcomes. Neither requires publishing hidden model reasoning.

## Learning objectives

By the end, you can:

- explain the critic's current approval rule and limitations;
- distinguish policy decisions from answer writing;
- define safe operational trace content;
- observe approved and blocked flows in the browser and API;
- compare pre-write evidence policy with post-write contract verification;
- test response parsing against malformed or unsafe trace shapes;
- propose stronger evidence checks without promising impossible guarantees.

## Critic as a policy boundary

The critic receives a question and `EvidenceBundle`, then produces:

```python
Critique(grounded: bool, query_coverage: float)
```

The current policy is intentionally simple:

```text
approve if at least one retrieval match exists
otherwise block
```

Query coverage is measured and displayed but is not an approval threshold. Separating the policy
into a role makes that limitation visible and replaceable.

A stronger critic might evaluate:

- minimum score and coverage;
- contradictory evidence;
- source recency or authority;
- claim-to-source entailment;
- required citations for each answer claim;
- domain policy or authorization.

Every added check needs false-positive/false-negative evaluation and a defined failure behavior.

## Critic and verifier are different gates

The UI now exposes two collaboration policies:

| Policy | Stages | Purpose |
| --- | --- | --- |
| `baseline` | planner → researcher → critic → writer | stable four-stage teaching contract |
| `verified` | planner → researcher → critic → writer → verifier | add post-write invariant checks |

The critic decides whether the available evidence permits writing. The verifier runs **after** the
writer and checks the candidate artifact against mechanical rules:

```text
expected citation count == writer-reported citation count
every unique evidence path appears as [path] in the answer
safe insufficient-evidence output has zero citations
```

If a rule fails, the verifier does not repair or return the candidate. It marks its stage blocked,
changes `grounded` to false, and substitutes a fixed server-controlled failure message. This is a
fail-closed output gate and a testable state transition.

These checks catch broken handoffs, citation loss, and incompatible writers. They do **not** prove
that a sentence is entailed by a source, that sources are correct, or that the corpus is complete.
Calling the feature “truth verification” would overstate what the implementation demonstrates.

## Safe trace versus chain-of-thought

| Safe operational trace | Do not expose as a trace |
| --- | --- |
| stage name and sequence | hidden free-form reasoning |
| completed/blocked status | private model chain-of-thought |
| evidence and document counts | secrets or authorization headers |
| bounded numeric coverage | complete private prompts |
| short predefined summary | internal system instructions |
| server-generated run ID | personal data from source documents |

Operational telemetry answers **what happened** and **where**. It should not pretend to reveal a
model's private internal reasoning. In this local deterministic workflow there is no model
chain-of-thought, but the same trace discipline keeps future provider integrations safe.

## Read the implementation

1. `CriticAgent`, `VerifierAgent`, and trace construction in [`collaboration.py`](../../backend/app/collaboration.py)
2. public trace schema in [`schemas.py`](../../backend/app/schemas.py)
3. browser runtime validation in [`api.ts`](../../frontend/src/api.ts)
4. trace rendering in [`App.tsx`](../../frontend/src/App.tsx)
5. malformed-response and safe-rendering tests in [`api.test.ts`](../../frontend/src/api.test.ts) and [`App.test.tsx`](../../frontend/src/App.test.tsx)

## Hands-on lab

### Step 1 — start the complete application

```bash
cp .env.example .env
docker compose up --build
```

Open <http://localhost:5173/?workflow=collaboration> (this deep-links straight to **Role-based multi-agent**).

### Step 2 — approved path

Ask:

```text
How does the example agent plan a project?
```

Capture or record:

- `run_...` identifier;
- grounded badge;
- planner, researcher, critic, writer order;
- critic `approved` and `query_coverage` metrics;
- source path and excerpt;
- writer citation count.

### Step 3 — blocked path

Ask:

```text
Explain quantum chromodynamics renormalization.
```

Verify:

- researcher reports zero evidence;
- critic is `blocked`;
- writer still completes by returning the safe fallback;
- sources and citation count are empty/zero;
- the page remains usable.

A blocked critic is a successful policy outcome, not a crashed request.

### Step 4 — inspect raw JSON

Use browser developer tools or curl. Confirm trace summaries are fixed operational statements and
metrics contain only finite numbers or booleans.

### Step 5 — verified output path

Open <http://localhost:5173/?workflow=verified> (or select **Verified multi-agent**) and repeat the
grounded question. Confirm:

- the workflow identifier ends in `-verifier`;
- the trace contains five ordered stages;
- verifier metrics report `approved`, `citation_paths_valid`, expected citations, and reported
  citations;
- the answer and source list remain plain text.

Then call the API directly:

```bash
curl --silent http://localhost:8000/api/v1/collaborate \
  --header 'Content-Type: application/json' \
  --data '{
    "question": "How does the example agent plan a project?",
    "workflow": "verified"
  }' | python3 -m json.tool
```

The verifier is not controlled by a browser-supplied stage list. The request chooses one of two
closed policies; the backend owns agent order, run ID, checks, outcomes, and fallback content.

### Step 6 — prove the browser rejects malformed traces

Run:

```bash
cd frontend
npm test -- --run src/api.test.ts
```

Review tests for:

- malformed run IDs;
- missing, duplicated, or out-of-order stages;
- unsupported agent names/outcomes;
- invalid metrics;
- wrong workflow or mode.

Also inspect the failure-injection test that injects an `UnsupportedWriter`. It proves a writer that
drops expected citations cannot make the verified workflow return its candidate answer.

Add one malformed fixture of your own and assert `invalid_trace`.

## Designing useful telemetry

A production trace often needs:

- request/run correlation ID;
- stage start/end timestamps and duration;
- attempt number;
- model/provider identifier when used;
- token/cost budget without prompt content;
- error code and retry decision;
- evidence identifiers rather than private excerpts;
- actor/tenant information in access-controlled logs only.

Before storing a field, define purpose, reader, retention, redaction, access control, and deletion.
“More observability” is not permission to retain every prompt.

## Exercises

### Required — trace threat model

For each current trace field, document:

- why a user or operator needs it;
- whether an external caller can influence it;
- maximum size/type enforcement;
- privacy risk;
- whether it belongs in the response, server logs, both, or neither.

### Intermediate — stronger approval rule

Design and test a minimum-coverage rule. Include at least:

- exact boundary;
- zero-token query behavior;
- a relevant paraphrase with low lexical overlap;
- an irrelevant high-overlap paragraph;
- user-visible abstention wording.

Compare errors before deciding a default.

### Advanced — contradiction state

Extend `Critique` conceptually from a boolean to `approved | insufficient | conflicting`. Define how
the writer, public schema, UI, and evaluation should react. Explain why “conflicting” should not be
silently flattened into a normal answer.

## Check your understanding

1. Why is blocked a valid outcome rather than an exception?
2. What does the current critic miss?
3. Why should a trace avoid complete prompts even when debugging is easier with them?
4. How does runtime browser validation reduce damage from a compromised or incompatible server?
5. Which telemetry belongs only in access-controlled operations logs?
6. Why does the verifier run after the writer rather than replacing the critic?
7. Which claim about answer quality would still be unjustified after all verifier checks pass?

## Completion checklist

- [ ] I observed approved and blocked paths in the browser.
- [ ] I compared baseline and verified traces.
- [ ] I inspected the raw JSON for both paths.
- [ ] I can state the critic's exact current rule.
- [ ] I added one invalid-trace parser test.
- [ ] I completed a trace-field threat model.
- [ ] I can distinguish operational trace data from chain-of-thought.
- [ ] I can explain the verifier's fail-closed behavior and its semantic limitations.

## Further reading

- [OpenTelemetry concepts](https://opentelemetry.io/docs/concepts/)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [React escaping and JSX](https://react.dev/learn/writing-markup-with-jsx)

---

**Previous: [Lesson 04](../04-typed-orchestration/README.md)** · **Next: [Lesson 06 — Evaluation, tests, and failure injection](../06-evaluation/README.md)**
