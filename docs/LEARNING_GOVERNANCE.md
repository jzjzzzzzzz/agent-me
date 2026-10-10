# Reviewed learning governance

The authenticated owner workbench now exposes local learning policy, retention and
exact memory consolidation. These controls do not invoke a model, automatically
confirm candidates, schedule background work, grant tool/disclosure permissions,
or perform semantic similarity merging. See [learning controls](LEARNING_CONTROL.md),
[identity and retention](IDENTITY_TIME.md) and [independent-copy erasure](ERASURE_REVIEW.md).

## Policies

Open **Manage learning governance** after unlocking the owner workbench. The two
advanced JSON editors contain the complete typed policy, not a partial replacement.
Unknown fields, duplicate JSON keys, invalid Unicode and out-of-range values are
rejected locally. Review the before/after policy and explicitly apply it. Requests
bind both the observed workspace owner and policy revision; a concurrent edit or
purge/reset rejects the old review even if the new workspace starts at revision 1.
Legacy callers may omit the additive owner precondition.

Learning controls include source kinds, privacy labels, candidate limit (1–100),
blocked key prefixes, and labels/prefixes requiring candidate revision. Empty
source-kind or label lists deny learning. Prefixes use the native normalized starts
matching rules. These controls govern candidate production, not confirmation or
external-provider disclosure consent. Retention has five nullable day fields;
`null` disables that category and enabled values are 1–365000 days. All retention
categories are disabled in a new workspace.

## Retention

1. Optionally enter an effective time in the browser's timezone; blank means now.
2. Create a persisted preview. This does not remove memories or create forgetting
   hashes. Only the latest 100 plans appear in this view; a plan is bounded to
   1000 targets by the native manager.
3. Review actual cascade counts and the precise target IDs/revisions. The server
   runs the real native application in a rolled-back savepoint, without committing
   the deletion, and returns a stable plan digest plus an affected-copy scope digest.
4. Explicitly acknowledge and apply both digests. The scope is recomputed inside
   the same write transaction as application. Newly linked relationships or
   modified retained linked copies invalidate the review even if the primary
   memory revision has not changed. Policy/target changes also reject execution.

The review binds removed full rows, historical revisions, origin/evidence cascades,
forgetting hash additions/refreshes and explicitly linked retained local copies.
It returns counts and opaque digests, not raw historical private bodies. Current
memory text is displayed only from the authenticated workbench's existing cache.
Independent notes/tasks, action plans/events, unrelated records, files, downloads,
exports and backups are not globally erased; use explicit copy erasure separately.
An already-applied exact immutable-plan replay returns the prior receipt with no
new effects; its old scope digest does not authorize fresh deletion.

Future plans are disabled based on the server observation clock. Refresh the
workbench once their effective time passes; the native manager also enforces the
actual server time. There is no timer or scheduler. Arithmetic near year 0001
safely treats an unrepresentable earlier cutoff as matching no records.

## Exact consolidation

Filter by confirmed entity, key prefix and memory kinds, then persist a preview.
Review every literal member, revision and selected keeper before acknowledging
and applying its digest. Grouping requires identical content and all native
privacy/time/confidence qualifiers; it is not model-assisted or semantic merging.
History and origins are preserved. A pending keeper remains pending, and member
revision changes invalidate dependent relationships/actions. Missing current
member revisions in the workbench cache disable application; the native manager
finally verifies fingerprints and revisions atomically.

Refresh, workspace/session changes and successful mutations invalidate reviewed
UI consent. Authentication failure locks the workspace; conflicts do not retry or
silently reauthorize. Nine locale dictionaries have completeness tests; non-English
labels remain machine-assisted and need native-speaker editorial review.

## CLI and HTTP

Ordinary native CLI governance commands use only the explicitly selected local
workspace; they do not load provider credentials or owner `.env` configuration:

```sh
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /path/to/workspace governance state
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /path/to/workspace governance retention-review PLAN_ID
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /path/to/workspace governance retention-apply PLAN_ID \
  --digest PLAN_SHA256 --scope-digest SCOPE_SHA256 --yes
```

Learning/retention `configure` accept `--expected-owner-id` alongside the required
policy revision. Existing direct native retention application remains available
for compatibility; the workbench uses only the stricter reviewed endpoint.

Authenticated, no-store HTTP additions:

- `GET /api/v1/personal/learning/governance`
- `GET /api/v1/personal/retention/plans/{id}/review`
- `POST /api/v1/personal/retention/plans/{id}/apply-reviewed`

Policy and retention/consolidation preview requests optionally accept
`expected_owner_id`; the workbench always sends it. No schema/export migration or
persisted plan-format change is required.

## Verification

Native tests cover atomic rollback, target/policy tampering, same-revision cascade
races, replay, independent copies, owner reset, earliest/future times, CLI and HTTP.
Typed frontend fixtures and component tests cover validation, owner binding,
explicit consent, authentication, refresh and locale changes. Isolated desktop and
mobile Chromium acceptance exercises real APIs for policy changes, exact pending
consolidation/history, and stale retention cascades followed by fresh review.
All test data is fictional; no live model or personal workspace is used.
