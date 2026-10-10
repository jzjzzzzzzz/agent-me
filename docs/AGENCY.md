# Local contextual agency

The independent owner Agent supports three real, bounded tools: `tasks.create`,
`tasks.complete`, and `notes.create`. They modify the private SQLite workspace, not a
mock tool log. No shell, browser, network, mail, filesystem-write plugin, or external
service is registered. Public chat/collaboration cannot invoke them. This is a local
single-owner capability, not delegated multi-user authentication.

## Know, recommend, act

`AgentRuntime.route(AgentIntent)` has a discriminated `intent.kind` contract:

- `ask`: local retrieval plus live atomic claim verification; returns `kind=knowledge`.
- `recommend`: validates data and records a recommendation with **no effects**; returns
  `kind=recommendation`. A recommendation cannot be approved or executed.
- `act`: records a permission-checked plan with **no effects**; returns `kind=action_plan`.
  The owner must separately inspect, approve, and execute it.

The outer intent overrides the invocation's intent. Source text, memory preferences,
provider prose, and a JSON argument saying `approved=true` cannot grant permission.
Unknown tools, fields, command arguments, and unknown intent types are rejected.

## Tool/data permissions

All three tools default to disabled. `Agency.configure` requires the current permission
revision and increments it. Each tool has a fixed workspace scope, an allowed sensitivity
label list, and an optional allowlist of confirmed entity IDs. An empty label list denies
all data; `entity_ids=null` allows all otherwise eligible entities, while `[]` excludes
entity-bound data. It does not exclude owner-entered, unbound text.

Arguments are typed and bounded: task titles <=160 characters, descriptions <=2000,
note content <=8000, and the serialized invocation <=65536 UTF-8 bytes. Due dates are
timezone-aware. An optional project must be a confirmed `project` entity. A completion
names an exact task revision. Sources are explicit memory IDs, not arbitrary file paths;
every source must currently be confirmed, known, valid, and owned by this workspace.

The effective output label cannot be lower than any declared input, source, target-task,
or linked entity label. The entity allowlist covers declared projects and source subjects.
Task completion inherits the target's source IDs, including live subject/privacy checks;
omitting them from an update request cannot bypass its original data boundary.
Arbitrary owner-entered text is not automatically classified or proved by source IDs.
Only the owner can declare it appropriate for a permitted label.

## Plan, approve, execute

A plan captures canonical arguments, workspace owner, source/entity revisions, tool
permission revision, and a SHA-256 digest. Approval must match both the plan revision
and the exact reviewed digest. Before approval and again under the execution write lock,
the Agent revalidates the plan digest, all live data, labels, target revision, entity scope,
and permission revision. Editing/deleting evidence or revoking/changing permission
invalidates the operation. The owner creates and reviews a new plan rather than silently
updating the approved plan.

The digest binds the reviewed plan; it is not a cryptographic signature against someone
who controls the host/database. Local process and database access are the owner boundary.

An idempotency key identifies one canonical requested operation. An identical replay
returns the existing plan even after execution or source removal; it creates no new effect.
The same key with different parameters is rejected. Concurrent executions serialize using
SQLite: actual effects, completed status, and success event commit in one transaction.
A completed execution replay only returns its previous result; it is not a new authorization.

Tool failures roll back all writes. A content-free failed event is persisted and the same
approved operation may be explicitly retried, with live preconditions rechecked. There
are at most three attempted executions; blocked preconditions do not consume attempts.
There is no automatic/background retry. Exception text never enters the plan or event.

## Inspect, cancel, undo

Plans expose calls, provenance IDs, reviewed revisions, outcomes, result IDs and minimal
undo metadata. Events expose stage/outcome/code/timestamp, not private reasoning.
Cancellation is available before successful execution. Successful actions use rollback:

- Creation deletes only the same owner's unchanged output created by that action.
- Completion restores only the prior status, creating a **new** monotonic task revision.
- Changed output blocks rollback rather than overwriting later effects.
- Repeated rollback is idempotent; permission revocation does not prevent owner cleanup.

Plans and notes/tasks can contain private owner-entered text. Deleting an evidence memory
blocks future execution but does not automatically purge independent task/note/plan copies.
Rollback removes an eligible created output, not the plan's arguments or audit events.
Snapshot export version `6` contains these private records. General portable import and
owner purging of independent action copies are tracked in the
[acceptance ledger](AGENT_IMPLEMENTATION.md); importing data must not silently restore
execution permissions or approved runnable operations.

## Authenticated API

All routes below use `/api/v1/personal`, the existing disabled-by-default owner bearer
authentication, request body limits, private validation redaction and `Cache-Control: no-store`.

| Method | Route | Body / result |
| --- | --- | --- |
| POST | `/agent` | `AgentIntent` -> typed knowledge/recommendation/action plan |
| GET | `/tools/permissions` | All default/current tool permissions |
| POST | `/tools/permissions/{name}` | `enabled`, `labels`, `entity_ids`, `expected_revision` |
| GET / POST | `/actions` | Inspect latest 100 plans / create `ToolInvocation` plan |
| POST | `/actions/{id}/approve` | Exact `expected_revision` and `digest` |
| POST | `/actions/{id}/execute` | Execute an approved plan; no body |
| POST | `/actions/{id}/rollback` | Reverse the exact unchanged effect |
| POST | `/actions/{id}/cancel` | Cancel a non-completed operation |
| GET | `/actions/{id}/events` | Inspect stage outcomes |
| GET | `/tasks`, `/notes` | Owner's local outputs |

API authentication represents owner authority; the approval endpoint is the explicit
approval operation. A future untrusted client needs separately delegated capabilities,
not this shared owner credential.

## Local CLI

No HTTP server, environment configuration, or model provider is needed. Choose a private
root with the global `--data-dir` option; never use a tracked directory for real owner data.

```bash
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo tools permissions
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo tools configure tasks.create \
  --expected-revision 1 --policy-json '{"enabled":true,"labels":["private"],"entity_ids":null}'
```

Write a fictional invocation to a local JSON file:

```json
{
  "tool": "tasks.create",
  "arguments": {"title": "Review fictional Orchid project"},
  "idempotency_key": "orchid-review-v1",
  "sensitivity": "private",
  "source_ids": [],
  "intent": "act"
}
```

```bash
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo action plan /tmp/invocation.json
# Inspect the returned arguments, permission/data revisions and digest before approval.
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo action approve PLAN_ID \
  --expected-revision 1 --digest REVIEWED_DIGEST
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo action execute PLAN_ID --yes
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo tasks
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo action events PLAN_ID
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo action rollback PLAN_ID --yes
```

`agent FILE` accepts the typed intent envelope; `action list`, `action cancel ID`, and
`notes` provide inspection/control. `--yes` is required for CLI execution and rollback;
it does not replace the approval digest.

## Evaluation

`make evaluate-agency` runs 17 disposable fictional cases: disabled defaults, separated
recommendations, no-effects plans, exact approval, real concurrent/idempotent execution,
replay conflicts, actual completion, safe undo, revocation, deletion, labels, subjects,
injection-as-data, atomic failure/retry, retry bounds, and inspectable provenance.
Core/API/CLI tests additionally cover malformed requests, tampering, stale source edits,
authentication, privacy-redacted errors, and export. A mutation regression demonstrates
that removing permission checks makes the evaluation fail.
