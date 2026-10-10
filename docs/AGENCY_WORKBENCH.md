# Owner-reviewed local action workbench

Open the private workspace with its owner token, open the review workbench, then choose
**Manage local tools & actions**. The pane loads on demand and exposes only the existing
`tasks.create`, `tasks.complete` and `notes.create` tools. It calls no model, shell, browser
automation or external service. [Native agency contracts](AGENCY.md) remain authoritative.

## Permission review is not execution

Each tool starts disabled. Choose its enabled state, allowed sensitivity labels and entity scope,
then open **Review permission change**. The before/after policy is shown explicitly. Nothing
changes until **Apply reviewed permission** sends the exact current permission revision.
The browser also sends the reviewed workspace owner ID. A workspace purge that resets permission
revisions cannot make an old owner's review apply to the new owner UUID. This additive
`expected_owner_id` precondition is optional for existing native/CLI/API clients; it is required by
the browser's review flow and is not persisted as policy or exported authority.

- All entities means all otherwise eligible subjects, not a bypass of labels or evidence checks.
- Only selected entities with an empty selection denies entity-bound data, not unbound owner text.
- No labels denies all data, even when the tool is enabled.
- Sensitive labels are an explicit permission choice; live source/subject/target label floors
  cannot be lowered by the proposal's declared label.
- A changed permission revision invalidates existing plans. Enabling the tool again does not
  restore authority for an old approved plan.

Draft permission edits disappear on a workbench mutation/refresh; an open policy review is
discarded when its editor changes. Locale changes keep the active operation draft but relabel UI
controls. Close/lock discards the pane's drafts and previews; nothing is saved in localStorage.
A token prop change creates a new keyed workbench session, aborting old requests and clearing all
identity/action/source drafts and previews before fresh data is accepted.

## Recommend, plan, approve, execute

1. Pick one of the three tools. The initial intent is **Recommendation only**, which can be
   recorded with the tool disabled but can never be approved or executed.
2. Enter typed arguments. Tasks have a title, optional description, optional project and optional
   due time interpreted in the browser's timezone. The canonical reviewed plan shows its actual
   timezone-aware timestamp. Notes require a title/content. Completion names an exact current task
   revision; it inherits that task's source lineage and privacy floor.
3. Optionally select confirmed known memory sources and inspect their literal text. Source IDs
   establish lineage, not semantic entailment of arbitrary owner-entered arguments. Current validity,
   subject scope and sensitivity are enforced by the backend, not inferred from a source instruction.
4. **Save proposal (no effects)** stores a recommendation or permission-checked action plan. It
   never creates/completes a task or note. The operation key/draft remain unchanged after success
   or a failed receipt: identical replay recovers the same plan. **New operation key** is a separate
   deliberate gesture, not an automatic retry or a silent way to duplicate effects. Reusing a key
   for changed parameters is rejected.
5. For a planned action, **Review plan** re-reads its current revision/status/digest. Inspect canonical
   arguments, effective label, permission/source/entity revisions, evidence text, operation key and
   exact digest. **Approve exact plan** approves that revision/digest and still has no tool effects.
6. **Review execution** is a new independent review. **Execute approved plan** performs the real
   local SQLite effect under live permission/data/target checks. A failed tool operation leaves no
   partial output and permits only an explicit reviewed retry, up to three attempted executions.
   A blocked precondition consumes no execution attempt. No automatic/background calls are added.

Completion includes already-completed tasks: such an operation can be a recorded no-op with
`changed=false`. Undoing a changed completion creates a new monotonic task revision; undoing a
no-op does not fabricate a task change. Current tasks and notes are displayed with output IDs,
revisions, labels, source IDs and creator-plan IDs. Plans show at most the latest 100 native records.

Canonical completion source lineage is limited to **20 total unique sources**, including inherited
and newly supplied IDs. An over-limit union is rejected before any plan/event persistence, rather
than writing a plan that cannot satisfy its response/approval contract. Overlapping IDs count once.

## Cancel, inspect, undo

**Review cancellation** allows cancellation of unexecuted recommendations/planned/approved/failed
actions. It does not delete a successful output. **Inspect action events** shows public stages,
outcomes and safe codes, not hidden reasoning or exception text.

For a completed operation, **Review rollback** shows its exact recorded output/revision. **Reverse
unchanged effect** removes only an unchanged output created by that action, or restores only a
changed completion's prior status. Any later output revision prevents overwriting or deleting it.
Owner rollback cleanup remains possible after tool permission revocation. Returned completion and
rollback receipts are checked against the original plan/owner/digest; malformed or foreign results
are not treated as successful reviewed actions.

Rollback does **not** remove plan arguments, audit/events, independent memory copies, chat or
exports. [Owner erasure controls](OWNER_CONTROL.md) separately delete outputs/actions/sources and
purge the workspace; CLI/API access remains available for these operations. Existing version-8
export includes local plans, permissions and outputs; import archives authority rather than
restoring executable approval.

## Live authority and client lifetime

The pane shares the workbench's single request mutex and abort session. Mutations immediately
invalidate open identity/action/evidence previews, including when the mutation subsequently fails;
successful refresh replaces them with current data. A local freshness check disables approval or
execution when displayed evidence/entity/permission revisions no longer match. The backend checks
again under its transaction; changes by another client after review yield a denial, not new effects.
Task/note arguments remain immutable once planned; a changed operation needs a new reviewed plan.
An aborted receipt does not trigger a follow-up refresh with the old credential session.

Lock, close and browser abort discard client previews/receipts, but do not guarantee cancellation
or undo of an already-started server mutation. Inspect current plans/outputs after unlocking instead
of assuming a missing receipt means no effect. Idempotency keys remain useful for that inspection.
Owner authentication/host filesystem access is the existing single-owner authority, not delegated
capabilities or multi-user isolation.

## Reproducible acceptance

`make test` checks shared fictional native/TypeScript contracts, malformed/foreign receipts,
default-off/no-effects behavior, independent gates, exact reviewed metadata, policy semantics,
explicit retry bounds, epoch invalidation, stale authority, unchanged-output rollback, literal HTML/
instruction rendering, authentication and locale-preserved drafts. The fictional JSON fixture was
generated from a disposable native `Agency`, including all plan states and actual task/note outputs;
it is not owner data. All nine UI locale dictionaries are type-complete; new labels are machine-assisted
and remain open to language review.

`make e2e` uses fresh desktop/mobile-emulated Chromium contexts and the guarded disposable API,
not the owner's browser profile or existing server. It exercises actual task creation/completion,
undo and note creation/deletion, recommendation cancellation, exact original source/entity versions,
idempotent plan replay, sensitive/entity scope rejection, permission revocation after execution
review, and later output changes blocking rollback. Browser requests are fenced to the fixture
origin; only named expected negative HTTP paths are allowed. Screenshots/reports stay in ignored
fixture artifact directories; temporary servers/workspaces are cleaned up. Hosted CI repeats the
browser, backend, Windows, minimum-Python, dependency, documentation and container gates.
