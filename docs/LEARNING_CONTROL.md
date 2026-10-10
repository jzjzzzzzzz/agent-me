# Owner learning policy and exact memory consolidation

Both components run independently of HTTP and providers. Every candidate still needs
explicit owner acceptance. Policy never enables automatic confirmation or tool execution.
Schema extension `6` introduced the typed policy and consolidation plans without changing
existing records, reviewed sources, task/note permissions, or action approvals.
Current export version `8` also includes portable owner-control and audit records.

## Learning policy

`LearningPolicyManager.settings/configure` exposes revisioned owner configuration:

| Field | Default | Effect |
| --- | --- | --- |
| `source_kinds` | All four supported kinds | Deny ingestion from kinds outside this list |
| `labels` | public/private/sensitive | Deny ingestion outside the effective source/entity label |
| `max_candidates` | 100 | Reject an entire extraction batch above the limit (1..100) |
| `blocked_key_prefixes` | [] | Reject an entire batch containing a matching memory key |
| `require_revision_labels` | [] | Require exact revision review for these memory/entity labels |
| `require_revision_key_prefixes` | [] | Require exact revision review for matching memory keys |

Prefixes compare after NFC normalization, trimming and case folding, not semantic inference.
Empty source/label lists deny all respective ingestion. Configuration requires the current
policy revision; stale updates fail without writes. Scope checks run inside the same write
transaction as ingestion, including before returning a completed replay. A completed replay
does not re-extract or learn new data. Batch limits/prefix rules apply to new extraction or
failed-run retry; policy changes do not silently edit or delete already accepted memories.

Denied source scope produces a permission error with no ingestion run. Invalid extraction
or candidate policy returns a content-free failed run with `error_code=extraction_invalid`;
retrying after owner policy correction reuses the stable run ID. No prefix match logs the
original text. This policy is an explicit boundary, not automatic PII/identity classification.

All confirmations remain owner operations. A strict label/key rule additionally requires
`expected_revision` and, when replacing conflicts, a complete `replace_revisions` map.
Current subject sensitivity is included even if it increased after memory creation.
Existing default revision-optional clients retain compatibility until the owner opts into
these stronger review rules.

## Exact cross-record consolidation

`ConsolidationManager.preview()` persists a no-effects plan, at most 100 groups/1000 records.
An optional `ConsolidationFilter` narrows by exact entity ID, case/NFC-aware key prefix and
allowed memory kinds; `kinds=[]` selects nothing. Other groups are not silently included.
It groups non-superseded records only when **every literal Entry field** matches: kind,
key, content, entity, sensitivity, belief, confidence, valid interval and occurrence time.
It does not merge paraphrases, infer equivalence, combine different periods, lower labels,
or resolve contradictions. An already confirmed record is preferred as keeper; otherwise
the earliest pending candidate is retained.

The preview captures IDs, revisions, canonical full-record fingerprints, owner and a digest.
The owner can inspect the member records and their revisions before applying the exact
reviewed digest. Any member edit, deletion or review invalidates the entire plan. All target
validation and effects occur under one write lock; a failed group rolls back every group.
Concurrent/repeated application is idempotent. Independently added records after preview
are not silently included in the approved snapshot.

Application creates a `corroborated` keeper revision and `superseded` member revisions.
Original records, history and origins remain inspectable/exportable. Exact source excerpts
are additionally copied into the keeper's origins without changing their source/run IDs,
document hash or spans. Pending keepers **remain pending**. No conflicting memory is
replaced by consolidation and no archived value is reactivated.

Relationships and action plans linked to previous exact revisions become stale; they are
not automatically re-approved just because text remained the same. Normal live evidence
checks apply. Consolidation is archiving, not erasure: deleting an archived member does not
delete an independently retained keeper/provenance copy. Use owner deletion on all relevant
copies or purge the stopped workspace when erasure, rather than deduplication, is intended.

## API and CLI

Private owner authentication, no-store responses and validation redaction apply throughout.

| Method | `/api/v1/personal` route | Contract |
| --- | --- | --- |
| GET | `/learning/policy` | Current settings |
| POST | `/learning/policy` | `{policy: LearningPolicy, expected_revision: int}` |
| POST | `/consolidation/preview` | Optional `{entity_id, key_prefix, kinds}` filter; default all; no effects |
| GET | `/consolidation/plans` | Latest 100 inspectable plans |
| POST | `/consolidation/{id}/apply` | `{digest: reviewed_digest}` |

```bash
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo learning policy
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo learning configure \
  --expected-revision 1 --policy-json '{"require_revision_labels":["sensitive"],"require_revision_key_prefixes":["identity.","profile."]}'
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo consolidate preview
# Optional narrow preview: consolidate preview --key-prefix project. --kind fact
# Inspect exact member records/revisions and retain the returned digest.
PYTHONPATH=backend .venv/bin/python -m app.agent_cli --data-dir /tmp/agent-me-demo consolidate apply PLAN_ID \
  --digest REVIEWED_DIGEST --yes
```

Tests cover source scopes, atomic limits/prefix denial, stale policy configuration, live
entity privacy, exact review/replacement, confirmed/pending keepers, copied origins,
concurrent replay, changed targets, all-group rollback and distinct qualifier exclusion.
`make evaluate-learning` now runs 24 reproducible fictional checks, including policy and
consolidation behavior; it never reads owner data or calls providers.
