# Reviewed snapshot migration and operational audit

Open **Review migration & audit** inside the private workbench. This exposes existing native
portable import, explicit private export and bounded read-only audit inspection. It never calls
a model, merges into occupied state, restores live execution authority, purges the workspace,
or uploads automatically when a file is selected. [Native owner contracts](OWNER_CONTROL.md)
remain authoritative; SQLite snapshots are not private Markdown/environment/filesystem backups.

## Destination and file review

The authenticated `/portability/state` reports the current workspace UUID, whether native import
preconditions consider it empty, the 16 MiB snapshot ceiling and the actual configured HTTP body
ceiling. Data, forgotten registries, archives, plans/outputs, configured policy or permission state
make the destination nonempty; initializer/access audit alone does not. Loading/import is disabled
when occupied, while audit/export remain available. Use a fresh destination deployment or existing
explicit owner controls; there is no silent purge or overwrite button in this pane.

Choose a local JSON file. Its size is checked before allocation, UTF-8 decoding is fatal, decoded
duplicate JSON keys and invalid surrogate escapes/nonfinite numbers are rejected. Only JSON
whitespace is removed at the outer boundary; a UTF-8 BOM is handled by the decoder. The source
version/owner are inspected locally, but the backend validates every native v6/v7/v8 data, integrity,
revision, timestamp, provenance and authority contract during preview.

**Original numeric tokens are preserved.** The browser keeps raw validated JSON rather than
re-serializing `JSON.parse`, which would round large integer revisions. Native Python receives the
original snapshot token stream. Both preview and approval wrapping are measured in actual UTF-8
bytes, including reviewed destination and the digest, before any upload. HTTP's limit can be smaller
than 16 MiB; larger supported files need the local CLI or an appropriately configured deployment.
Nothing is truncated. File names and raw contents are neither rendered nor audited by this pane.

Selection makes no upload. **Preview snapshot import** sends the chosen snapshot and reviewed
destination UUID; it displays source/destination owners, digest, collection counts and dispositions.
The owner then explicitly acknowledges trust in the original file's values/review states, counts,
authority handling and exact empty destination before **Import exact reviewed snapshot**.
Matching a digest is not authenticity or factual truth: preserved confirmed memories can become
answer evidence. Raw personal values/history are deliberately not reproduced in the review DOM.

Import preserves native data/IDs, owner binding and learning/retention policies. Source approvals
are revoked/incremented and require re-review. Tool, action, retention/consolidation and former
provider permissions become inert archive data; live tools/provider disclosure remain disabled.
Policies are not automatically applied. Successful import clears the loaded file and refreshes
all open panes under the adopted owner. Inert archives can be inspected via CLI/API or separately
deleted through the [erasure workbench](ERASURE_REVIEW.md).

## Destination binding and client lifetime

Native `preview/apply` accept optional `expected_destination_owner_id`; API payloads and CLI
`portability preview/import --expected-destination-owner-id` expose it. Browser always supplies it.
The UUID is re-read in the same transaction as emptiness checks and the import write. A purge/reset
that leaves the workspace empty again cannot redirect an old reviewed import. Return metadata
`destination_owner_id` records the pre-import target, distinct from the adopted snapshot owner.
Existing callers can omit this additive precondition. No persistent/export schema migration occurs.

File replacement/discard, mutation, refresh, Escape, close or token change invalidates review and
consent. The pane shares the workbench request mutex, abort session and epoch; no automatic retry
occurs. An ambiguous receipt must be investigated with current destination state, not replayed
as overwrite. A completed import makes the destination nonempty. Abort/lock cannot undo an already
started server import. Private raw data is held only in page/request memory, not localStorage;
discard means removing application references, not guaranteed physical memory sanitization.

## Audit and export

Audit loads the latest 100 content-free events; choose 100/500/1000 and explicitly reload. Displayed
fields are operation, actor, outcome, numeric counts and timestamp. No question, source/body/path,
credential/header, argument, parser/exception text or private reasoning is included. Owner mismatch
or malformed audit/receipt metadata fails closed. Audit is bounded, owner-removable operational
evidence, not a tamper-proof/security-attestation or comprehensive host/filesystem log. This pane
does not clear it automatically or turn it into model context.

**Download private snapshot** explicitly downloads `private-twin-export.json`. The response is checked
against the reviewed workspace owner and kept as original JSON text, preserving numeric tokens.
It is not rendered as HTML or echoed into audit. Downloaded files contain private data, remain on
the owner's filesystem and are outside later SQLite erasure scope. The project ignores this known
export filename; do not place other exports in tracked/public knowledge paths.

## Verification

Native/API/CLI tests cover metadata/limits/auth, configured/nonempty destinations, exact owner
preconditions through purge/reset, legacy omission, atomic owner/row rollback and shared native
dispositions. TypeScript tests cover duplicate/escaped keys, Unicode/nonfinite JSON, large integer
token preservation, pre-allocation bounds, exact wrapped byte counts, aborted reads, foreign owner/
count receipts and audit, separate consent, file replacement/refresh, explicit export and locales.

Fresh desktop/mobile Chromium fixtures perform real file import with preserved facts/binding,
revoked source approval, disabled tool/provider authority and inert archives; inspect redacted audit
and the actual private download; reject ambiguous JSON locally; and block a stale destination after
real purge. Contexts/services/data are disposable fictional fixtures, not an owner browser profile,
real workspace or model account. All nine dictionaries are complete/machine-assisted and open to
language review. Reports/screenshots/download artifacts stay outside Git/container contexts.
