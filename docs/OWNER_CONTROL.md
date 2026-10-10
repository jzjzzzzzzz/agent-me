# Portable owner control and operational audit

The Core, authenticated private API, and local CLI share one implementation. Public
endpoints never access it. Schema/export version `7` adds content-free audit, inert
import-authority archives and ingestion replay keys; migration preserves existing data
and tool state. This is a bounded personal-memory format, not a filesystem backup.

## Digest-reviewed portable import

`PortableMemory.preview(snapshot)` validates a version-7 snapshot (or supported version-6
legacy format) and returns an owner ID, collection counts, exact digest and explicit
authority dispositions. Preview does not write imported data. `apply(snapshot, digest)`
requires that reviewed digest and rechecks all destination preconditions under a write lock.

The target must be empty of owner records, histories, sources, tasks/notes, plans, archives,
forgetting registry and configured policies/permissions. Existing destination data is never
merged, overwritten or deduplicated silently. Initializer/access-only audit does not make a
new destination nonempty; it is replaced when adopting the imported workspace owner.
An import commits all rows, metadata, owner binding and import event atomically. Failure
rolls back owner adoption and every row. Concurrent imports commit at most once; a repeated
import into that now nonempty workspace fails rather than replacing data.

### Data and authority dispositions

| Category | Import behavior |
| --- | --- |
| Memories, revisions, transcripts, entities/relationships and histories | Preserve IDs, values, labels, confidence, belief, times and review states |
| Origins, forgetting digests, ingestion traces and replay keys | Preserve provenance and forgetting; do not execute/retry runs automatically |
| Owner binding and learning/retention policy | Preserve; policy application is still an explicit operation |
| Learning sources | Revoke approval, increment revision, preserve subject/label; owner re-review required |
| Task/note outputs | Preserve as independent owned data; do not re-run creation |
| Tool permissions and action/retention/consolidation plans/events | Move to an **inert authority archive**, never to live grant/plan tables |
| Prior import archives | Preserve as inert, owner-inspectable historical copies |
| Audit | Preserve up to the 10000-event operational bound, then append the import event |

All tools remain disabled in a fresh imported workspace. Old approval IDs cannot execute
or roll back; archive IDs are never routed to tools. Historical source approvals are also
inspectable in the archive. Re-approval starts a new source revision/campaign; old runs are
inspection history, not resumable permission. Version 7 retains exact original replay keys;
version 6 did not export them, so its imported runs receive deterministic archival keys.
Forgetting/deduplication still apply to new explicitly authorized ingestion.

The digest binds reviewed data, not its authenticity. An owner trusting a snapshot is
explicitly accepting its memory/review states; source-value verification does not prove
external truth. Archives are never retrieved as owner facts or treated as execution authority.

### Validation and bounds

The importer rejects mixed owners, duplicate/unbounded IDs or revision keys, unresolved
subjects/relationship evidence, latest-history mismatches, naive/non-monotonic timestamps,
inconsistent memory categories, unresolved origins or inaccurate excerpt spans/values,
incomplete/duplicate replay maps, malformed forgetting hashes, unknown schema fields,
invalid Unicode, nonfinite JSON values and unsupported versions. Error messages do not
include snapshot text. Historical references to deliberately erased records/runs may remain
opaque IDs; they are never used to revive a deleted record.

Input is bounded to 16 MiB, 10000 records per collection, 50000 total top-level records.
HTTP additionally respects the configured request-body ceiling, which may be smaller;
use local CLI for larger supported snapshots. The format preserves database state, not
private Markdown, environment files, provider credentials, filesystem ACLs or external data.
Move owner-maintained private Markdown separately using owner-controlled filesystem tools.

## Content-free audit

`AuditEvent` contains only server-generated operation name, actor (`core/api/cli`), outcome,
numeric aggregate counts, timestamp, random event ID and workspace owner ID. It stores no
questions, document text, source names, private paths, headers/tokens, tool arguments,
request bodies, exception messages or private reasoning. IDs/counts/timing are still private
metadata and are only available through owner-authenticated interfaces/export.

- Core source registration/review and ingestion outcomes/replays are audited. Writes and
  ingestion audit commit in the same transaction; denied attempts get a content-free event.
- Core personal retrieval audits evidence/context counts without question text.
- Authenticated HTTP operations audit static endpoint names and success/denial/failure;
  raw URL parameters are never stored. Invalid tokens/disabled mode and requests rejected
  before owner dependency resolution do not open the private store or create owner events.
- CLI operations audit static command/subcommand names, not arguments or file paths.
- Direct low-level `Store`/SQLite/filesystem access is trusted local-owner access, not an
  intercepted security boundary. It is not claimed to be comprehensively logged.

The log rotates to the newest 10000 events. Inspection is bounded to 1..1000 events.
Clearing replaces old events with a content-free clear event (API/CLI also record their
envelope operation). It is an owner-removable operational record, not a tamper-proof or
regulatory audit system. Existing learning traces and action events remain separate records.

## Explicit erasure of independent copies

Memory erasure and retention already purge the selected memory and its snapshots/origins,
with replay-aware forgetting digests. Independent copies require their own owner controls:

- **Task/note erasure:** exact current output revision; also removes live action plans/events
  that created or targeted that output, so retained plan arguments do not keep its copy.
- **Action-record erasure:** exact plan revision; by default retains independent outputs.
  Optional output erasure also requires its current revision. This is deletion, not rollback.
- **Source erasure:** exact source revision; removes registry metadata, source origins and
  runs. `forget_memories=true` additionally forgets memories linked through source origins,
  source revision history and explicitly restored descendants. Shared corroborated records
  are erased if linked to that source. Independent task/note/plan/archive copies remain.
- **Archive erasure:** removes that immutable historical authority copy, not imported facts.
- **History/audit clearing:** explicit separate operations; memory deletion does not erase
  unrelated transcript text or aggregate activity metadata.
- **Workspace purge:** exact workspace owner plus literal confirmation. Deletes **all SQLite
  state**, including archived copies, forgetting digests, histories, plans, outputs and
  policies, rotates the owner ID, disables tools and leaves only a content-free purge event
  (plus adapter audit envelopes). Response explicitly reports `scope=sqlite_state`.
  An in-flight legacy chat binds persistence to its starting workspace owner ID; a purge
  during generation discards the stale result instead of repopulating the new transcript.

Purge does not remove private Markdown or other files, `.env`/tokens, prior exports/backups,
Git history, provider-held data or already returned answers. Stop the service and remove the
owner's ignored workspace directory/token when full filesystem removal is intended. SQLite
`secure_delete` is enabled; it is not an encryption or physical-media sanitization guarantee.
Manual re-addition or a deliberately reviewed old export remains an explicit owner choice.

## Private API

All routes use `/api/v1/personal`, owner bearer authentication, private error redaction and
no-store responses. Successful data import/erasure never changes public fictional knowledge.

| Method | Route | Contract |
| --- | --- | --- |
| GET / POST | `/audit`, `/audit/clear` | Inspect `?limit=1..1000` / clear operational events |
| POST | `/portability/preview` | `{snapshot: exported_object}` -> digest/counts/dispositions |
| POST | `/portability/import` | `{snapshot: exported_object, digest: reviewed_digest}` |
| GET | `/portability/archives` | Latest 100 owner-only inert archives |
| POST | `/portability/archives/{id}/delete` | Erase one archive |
| POST | `/tasks/{id}/delete`, `/notes/{id}/delete` | `{expected_revision}` |
| POST | `/actions/{id}/delete` | `{expected_revision, purge_output?: false, expected_output_revision?: int}` |
| POST | `/sources/{id}/delete` | `{expected_revision, forget_memories?: false}` |
| POST | `/workspace/purge` | `{expected_owner_id, confirmation: "erase-personal-workspace"}` |

## CLI

Use a new private destination; real snapshots must remain outside Git-tracked paths.

```bash
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-original export /tmp/twin.json
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-new portability preview /tmp/twin.json
# Inspect counts/owner/dispositions; retain the exact returned digest.
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-new portability import /tmp/twin.json \
  --digest REVIEWED_DIGEST --yes
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-new portability archives
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-new audit events --limit 100
```

Owner commands additionally include `owner delete-output tasks|notes ID --expected-revision N`,
`owner delete-action ID --expected-revision N [--purge-output --expected-output-revision M]`,
`owner delete-source ID --expected-revision N [--forget-memories]`, `portability delete-archive ID`,
`audit clear`, and `owner purge --expected-owner-id OWNER_ID`. Every CLI erasure and import
requires `--yes`. It never calls HTTP or a provider.

`make evaluate-owner-control` runs 14 reproducible fictional checks. Core/API/CLI tests
also cover rich round trips, malformed snapshots, current revision review, concurrency,
all-write rollback, authority separation, rotation, private validation and deletion boundaries.
See the [connected-tool threat model](THREAT_MODEL.md).
