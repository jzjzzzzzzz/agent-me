# Scoped model-assisted literal learning

This optional HTTP/workbench adapter lets a configured model propose **kind/key classifications over
exact source quotations**. It is not unconstrained semantic synthesis, factual verification, automatic
acceptance or a background collector. Deterministic fields/paragraph extraction remains the default,
and the independent Agent core/CLI remains provider-free.

## Authority and data boundary

Source approval authorizes local learning, not network disclosure. A semantic attempt additionally
requires all of the following:

1. Owner-authenticated personal mode, an approved current source and current learning-policy scope.
2. Complete provider configuration plus an enabled, revision-reviewed disclosure policy bound to the
   exact endpoint/model fingerprint.
3. The `private` namespace and label, plus `sensitive` when the live source/subject floor requires it.
4. An **exact opaque source selector** in `document_paths`. `learning_selector(source_id)` returns
   `learning-source/<SHA256-of-source-ID>`. These reserved selectors never overlap public/private
   Markdown selection names and never perform file operations. Null/broad document allowlists do
   **not** authorize raw learning source delivery.
5. Per-request `allow_provider: true`, exact source/disclosure revisions, `reviewed_target_id` and
   `reviewed_content_hash` (SHA-256 of the actual UTF-8 source). Sensitive text also requires
   `allow_sensitive: true`. Public-labelled unreviewed input is conservatively private at delivery.

An entity allowlist additionally restricts a source's actual subject; an unbound source cannot satisfy
an explicit entity scope. No model output, source instruction, imported grant or memory preference
can provide these permissions. Only the consented source text and fixed extraction instructions enter
the model body. Source names, entity labels, other memory, private knowledge and transcripts are not
added. The complete source plus instructions must fit `MAX_CONTEXT_CHARS`, and source content still
obeys 80,000 codepoints/200,000 UTF-8 bytes. No truncation silently changes the consented source.

The existing disclosure policy is shared with optional legacy private-chat generation: its private
label/target can also authorize an explicitly opted-in private **question** under that older contract.
Opaque learning selectors do not grant Markdown/memory context. The semantic adapter checks its own
exact source scope; changing this policy is not a new default-on chat or learning switch.

## Proposals and provenance

The provider returns only JSON shaped as:

```json
{"candidates":[{"kind":"fact","key":"identity.name","quote":"Alex Example"}]}
```

Each kind is fact/preference/event/decision; keys are bounded to 100 codepoints and quotes to 2,000.
Unknown metadata (identity IDs, labels, confidence, dates, review status or approvals), duplicate JSON
fields, invalid Unicode, whitespace-only/trimmed-boundary changes, hallucinated or paraphrased text
and invalid offsets invalidate the **entire batch**. A unique quote is located exactly; repeated text
requires an explicit zero-based Unicode-codepoint `start` that matches the original source. Empty
candidates are valid abstention, not an invented memory or a retrying background operation.

The server inherits subject/sensitivity from current source authority, assigns all timestamps, and
uses only owner-declared validity/occurrence qualifiers. The model cannot fabricate event time or a
confidence probability. Every new candidate is pending; existing deduplication, conflict reporting,
revision-sensitive review, source origins, policy limits and replay-aware forgetting remain in force.
Exact quotation is provenance, **not polarity, attribution, entailment or external truth**. The owner
must review the proposed field and quotation in the full source context, including negation/other
people. The workbench retains that original source draft after success for this purpose, only in page
memory, until changed/closed/locked. It does not add a raw-document persistence store.

Runs use source format `mode: notes` and the authoritative extractor identifier
`model-literal-spans-v1/<provider-target-fingerprint>`. This distinguishes model-selected literal spans
from `exact-excerpts-v1` paragraphs; the UI displays both fields. Origins retain the **original input's**
UTF-8 SHA-256 digest, exact codepoint intervals and quotation, not a generated carrier document.
The existing version-8 export stores these runs/origins without new fields or live authority. Portable
import preserves their historical data but archives prior disclosure grants, disables the live policy
and revokes source approvals. It does not resume a provider call or restore its permission.

## Transaction, replay and failure semantics

Delivery authorization takes a short snapshot/write transaction and records content-free metadata.
No network I/O runs while a SQLite writer lock is held. After delivery, current source, owner,
subject revision/label, learning-policy revision, disclosure-policy revision and provider target are
revalidated before storage, under `BEGIN IMMEDIATE`. Changed/revoked/deleted authority prevents any
candidate/origin writes. Data already delivered to a provider cannot be recalled by a later revocation.

A completed matching source/revision/document/format/extractor/declared-time run is returned as a
replay **without another provider call**, but only after fresh source/disclosure authority checks.
Deleted memories are not recreated by returning old run metadata. Changed target/source revisions
start distinct campaigns; forgetting digests still constrain their contents. Provider credentials/model
aliases are not proof of an immutable model version or provider authenticity.

Malformed proposal batches become durable `extraction_invalid` runs with no partial memory effects.
Storage failures roll back the entire batch, record a content-free `storage_failed` run and support
explicit same-input retry with the same run ID/incremented attempts. Classified transport/envelope
errors return the existing safe provider error and a content-free audit event; no raw provider error
or response is stored. These pre-extraction failures are audited, **not** represented as completed
extraction runs. The owner retries explicitly; there is no automatic provider retry loop.

## Owner interfaces

All routes require the personal owner token:

| Method | `/api/v1/personal` route | Contract |
| --- | --- | --- |
| GET | `/learning/sources/{id}/semantic-review` | Approved source revision, exact selector, opaque configured target, policy revision, scope availability, effective delivery label and whole-source character budget; no credentials/URL |
| POST | `/learning/sources/{id}/ingest-semantic` | Exact source text, `mode: notes`, reviewed source/policy revisions, target/content hashes, explicit provider/sensitive consent and optional declared temporal fields |

Configure credentials through the deployment's existing ignored environment, obtain the target and
selector from the authenticated review route, then review a policy with the private namespace/labels
and `document_paths: ["learning-source/<reviewed-source-hash>"]`. The CLI's existing `disclosure configure`
command can manage this policy, but never calls a provider itself. Do not substitute an arbitrary
Markdown filename for the exact selector returned by the server.

In the workbench choose **Model-assisted quotations**. Without configuration/exact policy scope the
send consent remains disabled. Consent is cleared when source/text/mode changes and after each
attempt; sensitive opt-in is separate. A successful result still requires candidate confirmation.
The source remains in the local draft while you review; fields/paragraph modes retain their local
behavior. Closing/locking cancels client delivery/receipt but cannot guarantee rollback of an already
started server operation; revoking source/policy authority blocks stale storage.

## Verification scope

Core/API tests inspect actual mock-HTTP request bodies, exact original origins, Unicode/repeated
spans, whole-record budgets, malformed/forged proposals, empty abstention, source/target/policy/entity
revocation races, failed-batch rollback/retry, completed-call replay, forgetting and inert portable
import. Desktop/mobile-emulated Chromium acceptance sends real UI requests to an owned loopback
scripted model, checks the browser's real SHA-256 consent binding, confirms no unrelated memory or
source registry name enters that model body, and verifies pending records/origins and consent reset.
The fixture model-control route exists only inside the guarded disposable helper; it accepts only a
startup-pinned loopback mock target and synthetic credentials, never an owner model URL or key.

Scripted model responses verify the **contract and data flow**. They do not measure an actual LLM's
semantic precision/recall, human-review workload or generalization. Those require independently
labelled data and separately authorized model runs; no real owner account/data was used in these
regression checks.
