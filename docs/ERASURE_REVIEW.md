# Exact, owner-reviewed independent-copy erasure

Open **Review stored-data erasure** in the private workbench to erase task/note outputs, action
records, learning sources or inert import archives. This targets persistent SQLite copies, not
tool rollback, semantic search-and-delete, files, exports, backups or provider-held copies.
The [existing owner controls](OWNER_CONTROL.md) remain available through Core/API/CLI.

## Select, preview, review, apply

The snapshot-consistent owner-bound catalogue returns IDs/revisions/labels, not task/note bodies,
action arguments, source excerpts or archive authority. Action/archive choices show the latest 100;
task/note/source choices follow existing native lists. **Cascading scope never uses that UI limit**:
output deletion finds every associated plan/event, including older plans absent from the catalogue.

| Target | Default and explicit choices |
| --- | --- |
| Task/note output | Remove its current output, creator and every plan/event whose result or completion target references it |
| Action record | Remove that plan/events, keeping its output. Explicit output purge separately reviews the output's **current**, not old execution, revision and all associated plan/event copies |
| Learning source | Remove registry/origins/runs, keeping memories. Explicit forgetting also removes source-linked/restored descendants, all their revisions/origins/digests and evidence-linked relationship history |
| Import archive | Remove that inert historical authority archive only; imported live data/current permissions remain unchanged |

**Preview exact erasure scope** shows removed rows, refreshed/added anti-relearning hashes and
explicit retained lineage copies. References contain table, ID, optional revision, label and opaque
primary-key fingerprint; historical raw content/arguments are not echoed. Counts are stored rows,
not proof that one concept has only one copy. Source scope reports kept tool copies, linked receipts
and other source registrations; action-only scope reports its kept output. Unlisted unrelated data,
drafts, chats, entities, independent files and backups remain. Archive scope does not inventory all
imported live records. Identical free text in an unrelated note is not inferred to be linked.

Expand lists and inspect exact target/options/digest. No mutation commits until the owner checks the
scope/boundary acknowledgement and chooses **Erase exact reviewed scope**. Changing choices, Escape,
refresh or a workbench mutation discards preview/consent. The shared mutex/abort/epoch session rejects
stale previews; token changes remount it. Failed apply never silently retries or preserves consent.

Successful erasure refreshes open panes. A removed selected source clears its source draft; removed
memories close their current correction/delete drafts. Other unlinked inputs may remain until changed,
closed or locked. Abort cannot undo an already-started server erasure; inspect current data instead
of inferring no effect from a missing receipt.

## Native scope proof

`ReviewedErasure` runs independently of HTTP, settings and providers. It uses the **same actual
deletion helper** as legacy owner operations, not a separate approximate cascade implementation:

1. Enter `BEGIN IMMEDIATE`; require the reviewed owner UUID/target revision. Snapshot registered
   erasure tables using their actual SQLite primary keys, including composite revision keys.
2. Resolve a requested current action-output revision and return it as reviewed request metadata.
3. Run real deletion inside a savepoint; compute removed/changed/added rows and retained explicit
   lineage copies; roll back/release the savepoint. Preview changes no committed state or audit.
4. Hash exact parameters and full affected/retained **pre-mutation** snapshots locally. Only
   references/hash leave the core. Generated forgetting timestamps are not authority; deterministic
   hash keys/pre-existing refreshed hashes have stable scope, even with a frozen equal timestamp.
5. Apply recomputes scope under the same write lock. Changed arguments, revisions, new linked
   plans/events/restores/origins/receipts or retained copies reject the digest without partial effects.
   Unrelated rows and permission revocation do not block owner cleanup.
6. Run real deletion and its content-free owner audit event once, then commit atomically.

Preview can briefly serialize writers; no network work occurs under the lock. It persists no preview
authority. Content-free operational audit is excluded from the digest so reads cannot invalidate
their own preview; related **action events** are included. No schema/export/version migration occurs.
Legacy revision-only deletion remains compatible and does not gain a digest guarantee automatically.

## API and CLI

All routes require the owner token and `Cache-Control: no-store`:

| Method | `/api/v1/personal` route | Contract |
| --- | --- | --- |
| GET | `/owner/erasure/catalogue` | Owner UUID and metadata-only choices |
| POST | `/owner/erasure/preview` | `ErasureRequest` → `ErasurePreview` |
| POST | `/owner/erasure/apply` | `{request: returned_request, digest}` → deletion/count receipt |

Example explicit private request file:

```json
{"kind":"source","id":"REVIEWED_SOURCE_ID","expected_owner_id":"REVIEWED_OWNER_UUID","expected_revision":2,"purge_output":false,"expected_output_revision":null,"forget_memories":true}
```

```bash
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo owner preview-erasure /tmp/erasure-request.json
# Inspect the full scope. For action-output purge, copy the returned normalized request
# with its resolved expected_output_revision into the private request file before apply.
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo owner apply-erasure /tmp/erasure-request.json \
  --digest REVIEWED_SCOPE_SHA256 --yes
```

CLI reads only the named request file (65,536-byte limit), outputs JSON and requires `--yes` plus
the reviewed digest to apply. Invalid/stale/unconsented input exits `2`; success exits `0`. No owner
environment/provider credentials are loaded. Global `owner purge` and portable import/export are
separate existing controls, not hidden selective-erasure buttons.

## Evidence

Native/API/CLI tests prove unchanged preview state/audit, every mode, unlimited plan cascades,
current output revision review, restored/cross-source history, retained copies, changed links/body/
events/archive, stable forgetting hashes, unrelated mutations, revoked-permission cleanup, strict
input/auth and actual failure rollback. Fictional native fixtures are parsed by TypeScript. DOM
tests cover separate consent, choice/epoch invalidation, exact count receipts, stale handling,
keyboard cancellation, authentication and locale-preserved choices.

Production desktop/mobile fixture acceptance performs real cascading output deletion with a stale
new-link denial, unrelated identical-text survival, source/restoration/relationship erasure with kept
notes/actions, separate action-only/output deletion, source-draft cleanup and inert archive deletion
after real portable import. Requests remain on the owned fixture origin; only exact expected negative
paths bypass the error fence. Data/screenshots are fictional, not owner data/browser profiles; no
real model account is used. All nine locale dictionaries are type-complete, machine-assisted and
open to language review.
